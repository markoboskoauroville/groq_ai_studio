// KeyPool.swift: the Groq key pool with failover, a port of groq_pool.DynamicKeyPool (Phase A, 14.11.2026).
// Same files, same formats, so nothing is lost and the Python backend sees the same state:
//   ~/.groq/keys.txt        noise-tolerant, one gsk_ key per line when written
//   ~/.groq/.env            GROQ_API_KEY=... (added as a fallback, never written)
//   ~/.groq/key_state.json  {"current": "<sha256[:12]>", "cooldown": {"<id>:<model>|<id>:*": <epoch until>}}
// Both pools read the files before every decision (the Python side does too since Phase A), so a cooldown written by one
// is seen by the other. A key is never printed or logged: only its mask (gsk_ab...wxyz) or its id leave this file.
import Foundation

let REJECTED_COOLDOWN = 30.0 * 24 * 3600     // a 401/403 key: retry in 30 days
let DEFAULT_RATE_COOLDOWN = 60.0

final class KeyPool {
    private let cfg: QueenConfig
    private let lock = NSRecursiveLock()
    private(set) var keys: [String] = []
    private var current: String?
    private var cooldown: [String: Double] = [:]

    init(_ cfg: QueenConfig) {
        self.cfg = cfg
        lock.lock(); reload(); lock.unlock()
    }

    private var keysFile: String { cfg.groqDir + "/keys.txt" }
    private var stateFile: String { cfg.groqDir + "/key_state.json" }

    static func id(_ key: String) -> String { String(sha256hex(key).prefix(12)) }
    static func mask(_ key: String) -> String { key.count >= 10 ? "\(key.prefix(6))...\(key.suffix(4))" : key }

    /// extract_keys_from_noise: every gsk_ key in any text (.txt, .env, JSON, exports, logs), cleaned, de-duplicated.
    static func extract(_ text: String) -> [String] {
        guard !text.isEmpty, let re = try? NSRegularExpression(pattern: "gsk_[A-Za-z0-9_-]+") else { return [] }
        let ns = text as NSString
        var out: [String] = []
        let strip = CharacterSet(charactersIn: "-_'\",.;:()[]{}")
        for m in re.matches(in: text, range: NSRange(location: 0, length: ns.length)) {
            var k = ns.substring(with: m.range)
            while let last = k.unicodeScalars.last, strip.contains(last) { k.removeLast() }
            if k.hasPrefix("gsk_") && k.count >= 20 && !out.contains(k) { out.append(k) }
        }
        return out
    }

    private func envKey() -> String {
        if let v = ProcessInfo.processInfo.environment["GROQ_API_KEY"], !v.isEmpty { return v }
        guard let text = Files.read(cfg.groqDir + "/.env") else { return "" }
        for raw in text.components(separatedBy: .newlines) {
            var l = raw.trimmingCharacters(in: .whitespaces)
            if l.hasPrefix("export ") { l = String(l.dropFirst(7)).trimmingCharacters(in: .whitespaces) }
            guard l.hasPrefix("GROQ_API_KEY") else { continue }
            guard let eq = l.firstIndex(of: "=") else { continue }
            var v = String(l[l.index(after: eq)...]).trimmingCharacters(in: .whitespaces)
            if let hash = v.range(of: " #") { v = String(v[v.startIndex..<hash.lowerBound]) }
            return v.trimmingCharacters(in: CharacterSet(charactersIn: "\"' "))
        }
        return ""
    }

    /// keys.txt + GROQ_API_KEY, then key_state.json.
    func reload() {
        lock.lock(); defer { lock.unlock() }
        var ks = KeyPool.extract(Files.read(keysFile) ?? "")
        let e = envKey()
        if !e.isEmpty && e != "your_api_key_here" { ks += KeyPool.extract(e) }
        var seen = Set<String>()
        keys = ks.filter { seen.insert($0).inserted }
        loadState()
    }

    private func loadState() {
        if let d = Files.readJSON(stateFile) as? [String: Any] {
            current = d["current"] as? String
            var cd: [String: Double] = [:]
            for (k, v) in (d["cooldown"] as? [String: Any]) ?? [:] {
                if let n = v as? NSNumber { cd[k] = n.doubleValue }
            }
            cooldown = cd
        } else {
            current = nil
            cooldown = [:]
        }
        let ids = keys.map(KeyPool.id)
        if keys.isEmpty { current = nil } else if current == nil || !ids.contains(current!) { current = ids[0] }
    }

    private func saveState() {
        let o: [String: Any] = ["current": current.map { $0 as Any } ?? NSNull(), "cooldown": cooldown]
        _ = Files.writeJSON(stateFile, o, privateFile: true)
    }

    private func saveKeys() {
        let text = keys.isEmpty ? "" : keys.joined(separator: "\n") + "\n"
        Files.writeAtomic(keysFile, Data(text.utf8), privateFile: true)
    }

    // ------------------------------------------------------------ the pool
    func addKeys(_ new: [String]) -> (added: Int, total: Int) {
        lock.lock(); defer { lock.unlock() }
        reload()
        let before = keys.count
        for k in new where k.hasPrefix("gsk_") && k.count >= 20 && !keys.contains(k) { keys.append(k) }
        saveKeys()
        loadState()
        return (keys.count - before, keys.count)
    }

    func remove(id keyId: String) -> Bool {
        lock.lock(); defer { lock.unlock() }
        reload()
        guard let idx = keys.firstIndex(where: { KeyPool.id($0) == keyId || KeyPool.mask($0) == keyId || $0 == keyId }) else {
            return false
        }
        let removed = keys.remove(at: idx)
        let kid = KeyPool.id(removed)
        for k in cooldown.keys where k.hasPrefix(kid + ":") { cooldown.removeValue(forKey: k) }
        if current == kid { current = keys.first.map(KeyPool.id) }
        saveKeys()
        saveState()
        return true
    }

    func remove(index: Int) -> Bool {
        lock.lock(); defer { lock.unlock() }
        reload()
        guard index >= 1 && index <= keys.count else { return false }
        return remove(id: KeyPool.id(keys[index - 1]))
    }

    func clear() {
        lock.lock(); defer { lock.unlock() }
        keys = []
        saveKeys()
        current = nil
        cooldown = [:]
        saveState()
    }

    func reset() {
        lock.lock(); defer { lock.unlock() }
        reload()
        cooldown = [:]
        if let k = keys.first { current = KeyPool.id(k) }
        saveState()
    }

    private func ordered() -> [String] {
        guard !keys.isEmpty else { return [] }
        let ids = keys.map(KeyPool.id)
        let start = current.flatMap { ids.firstIndex(of: $0) } ?? 0
        return Array(keys[start...] + keys[..<start])
    }

    private func waitFor(_ key: String, _ model: String) -> Double {
        let kid = KeyPool.id(key)
        let until = max(cooldown["\(kid):*"] ?? 0, cooldown["\(kid):\(model)"] ?? 0)
        return max(0, until - Clock.now)
    }

    /// The keys to try, the current one first; cooling keys left out unless every key is cooling (strict: never).
    func candidates(_ model: String, strict: Bool = false) -> [String] {
        lock.lock(); defer { lock.unlock() }
        reload()
        let o = ordered()
        let ready = o.filter { waitFor($0, model) <= 0 }
        return strict || !ready.isEmpty ? ready : o
    }

    /// The key failed. rejected (401/403): every model, 30 days. Anything else: this model, Retry-After (min 5 s, 60 s).
    func cool(_ key: String, _ model: String, status: Int, retryAfter: String?) {
        lock.lock(); defer { lock.unlock() }
        reload()
        let kid = KeyPool.id(key)
        let scope: String
        var seconds: Double
        if status == 401 || status == 403 {
            scope = "*"
            seconds = REJECTED_COOLDOWN
        } else {
            scope = model
            seconds = DEFAULT_RATE_COOLDOWN
            if let r = retryAfter, let v = Double(r.trimmingCharacters(in: .whitespaces)) { seconds = v }
            seconds = max(seconds, 5)
        }
        cooldown["\(kid):\(scope)"] = Clock.now + seconds
        if let other = keys.first(where: { $0 != key }) { current = KeyPool.id(other) }
        saveState()
    }

    func good(_ key: String, _ model: String) {
        lock.lock(); defer { lock.unlock() }
        reload()
        let kid = KeyPool.id(key)
        var changed = current != kid
        current = kid
        if cooldown.removeValue(forKey: "\(kid):\(model)") != nil { changed = true }
        if changed { saveState() }
    }

    func statusRich() -> [[String: Any]] {
        lock.lock(); defer { lock.unlock() }
        reload()
        let now = Clock.now
        var items: [[String: Any]] = []
        for (i, key) in keys.enumerated() {
            let kid = KeyPool.id(key)
            let active = kid == current
            var cds: [[String: Any]] = []
            for name in cooldown.keys.sorted() {
                guard name.hasPrefix(kid + ":"), let until = cooldown[name], until > now else { continue }
                let scope = String(name.dropFirst(kid.count + 1))
                cds.append(["scope": scope, "seconds_left": Int(until - now)])
            }
            let type: String, text: String
            if let c = cds.first {
                type = "cooling"
                text = "Cooling (\(c["scope"]!), \(c["seconds_left"]!)s)"
            } else if active {
                type = "active"
                text = "Active (Primary)"
            } else {
                type = "ready"
                text = "Ready (Failover Pool)"
            }
            items.append(["index": i + 1, "id": kid, "masked": KeyPool.mask(key), "status": text, "state_type": type,
                          "is_active": active, "cooldowns": cds])
        }
        return items
    }

    func statusLegacy() -> [[Any]] {
        statusRich().map { [$0["index"]!, $0["masked"]!, $0["status"]!] }
    }

    var count: Int { lock.lock(); defer { lock.unlock() }; reload(); return keys.count }
    var first: String? { lock.lock(); defer { lock.unlock() }; reload(); return keys.first }
}
