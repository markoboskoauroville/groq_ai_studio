// Queen.swift: the window's line to Queen, the Python server of Groq AI Studio on 127.0.0.1:8765 (~/.groq).
// The server stays the brain (keys, skills, routes, chats); this app is its native face (Marko, 14.11.2026: "now it is
// time to convert our Grok AI Studio into a Swift app"). Down at start: started the way `qwen` starts it.
import Foundation
import AppKit

struct Msg: Identifiable, Equatable {
    let id = UUID()
    var role: String
    var content: String
}

struct ChatMeta: Identifiable, Equatable {
    let id: String
    let title: String
    let count: Int
    let updated: String
}

final class Queen: ObservableObject {
    static let shared = Queen()

    @Published var up = false
    @Published var line = "looking for Queen"
    @Published var version = ""
    @Published var model = ""
    @Published var keys = 0
    @Published var cooling = 0
    @Published var spent: Double = 0
    @Published var chats: [ChatMeta] = []
    @Published var messages: [Msg] = []
    @Published var chatId = Queen.newId()
    @Published var busy = false
    @Published var starting = false

    private var startedPid: Int = 0
    private var task: Task<Void, Never>?
    private var timer: Timer?
    private let home = FileManager.default.homeDirectoryForCurrentUser.path

    /// "v5" -> "5" (the window writes the v itself)
    static func bare(_ v: String) -> String { v.hasPrefix("v") ? String(v.dropFirst()) : v }

    static func newId() -> String { "s_" + String(Int(Date().timeIntervalSince1970 * 1000)) }

    var base: String {
        let f = home + "/.groq/app_url"
        if let s = try? String(contentsOfFile: f, encoding: .utf8) {
            let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
            if t.hasPrefix("http://127.0.0.1") || t.hasPrefix("http://localhost") { return t }
        }
        return "http://127.0.0.1:8765"
    }

    private var token: String {
        ((try? String(contentsOfFile: home + "/.groq/api_token", encoding: .utf8)) ?? "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func request(_ path: String, body: [String: Any]? = nil, timeout: Double = 15) -> URLRequest? {
        guard let url = URL(string: base + path) else { return nil }
        var r = URLRequest(url: url, timeoutInterval: timeout)
        if !token.isEmpty { r.setValue(token, forHTTPHeaderField: "X-Queen-Token") }
        if let body = body {
            r.httpMethod = "POST"
            r.setValue("application/json", forHTTPHeaderField: "Content-Type")
            r.httpBody = try? JSONSerialization.data(withJSONObject: body)
        }
        return r
    }

    private func json(_ path: String, body: [String: Any]? = nil, timeout: Double = 15) async -> [String: Any]? {
        guard let r = request(path, body: body, timeout: timeout) else { return nil }
        do {
            let (d, _) = try await URLSession.shared.data(for: r)
            return try JSONSerialization.jsonObject(with: d) as? [String: Any]
        } catch {
            return nil
        }
    }

    // ---------------------------------------------------------------- life
    func start() {
        linkAxread()
        Task { @MainActor in
            await self.refresh()
            if !self.up { self.startServer() }
            await self.loadChats()
        }
        timer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in
            Task { @MainActor in await self?.refresh() }
        }
    }

    /// ~/.local/bin/axread -> the axread inside this app, so Queen's ax_read.py finds the Swift reader.
    func linkAxread() {
        let fm = FileManager.default
        let inner = Bundle.main.bundlePath + "/Contents/MacOS/axread"
        guard fm.isExecutableFile(atPath: inner) else { return }
        let dir = home + "/.local/bin"
        let link = dir + "/axread"
        try? fm.createDirectory(atPath: dir, withIntermediateDirectories: true)
        if let dest = try? fm.destinationOfSymbolicLink(atPath: link), dest == inner { return }
        if (try? fm.attributesOfItem(atPath: link)) != nil {
            // only a link we made is replaced; a real file someone put there stays
            guard (try? fm.destinationOfSymbolicLink(atPath: link)) != nil else { return }
            try? fm.removeItem(atPath: link)
        }
        try? fm.createSymbolicLink(atPath: link, withDestinationPath: inner)
    }

    @MainActor
    func refresh() async {
        if let s = await json("/api/app/status", timeout: 4), (s["ok"] as? Bool) == true {
            up = true
            starting = false
            version = Queen.bare("\(s["version"] ?? "")")
            model = (s["model"] as? String) ?? ""
            keys = (s["keys"] as? Int) ?? 0
            cooling = (s["cooling"] as? Int) ?? 0
            spent = (s["total_spent"] as? Double) ?? Double("\(s["total_spent"] ?? 0)") ?? 0
            line = "running"
        } else if let h = await json("/health", timeout: 4), (h["ok"] as? Bool) == true {
            // an older Queen without /api/app/status
            up = true
            starting = false
            version = Queen.bare("\(h["version"] ?? "")")
            model = (h["default_model"] as? String) ?? ""
            line = "running"
        } else {
            up = false
            line = starting ? "starting" : "not running"
        }
    }

    /// The same command `qwen` runs (~/.groq/qwen), detached, keyboard on /dev/null, no browser tab, no Claude session variables.
    func startServer() {
        let qwen = home + "/.groq/qwen"
        guard FileManager.default.isExecutableFile(atPath: qwen) else {
            line = "not installed (~/.groq/qwen missing: run install.sh in groq_ai_studio)"
            return
        }
        starting = true
        line = "starting"
        let log = home + "/.groq/qwen_app.log"
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/sh")
        p.arguments = ["-c", "nohup \"$0\" < /dev/null >> \"$1\" 2>&1 & echo $!", qwen, log]
        var env = ProcessInfo.processInfo.environment
        for k in env.keys where k.hasPrefix("CLAUDE") { env.removeValue(forKey: k) }
        env["QWEN_NO_BROWSER"] = "1"
        env["PATH"] = home + "/.groq:" + home + "/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
        p.environment = env
        let out = Pipe()
        p.standardOutput = out
        p.standardError = FileHandle.nullDevice
        p.standardInput = FileHandle.nullDevice
        do {
            try p.run()
            p.waitUntilExit()
            let s = String(decoding: out.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
            startedPid = Int(s.trimmingCharacters(in: .whitespacesAndNewlines)) ?? 0
        } catch {
            starting = false
            line = "could not start: \(error.localizedDescription)"
        }
    }

    /// OFF: what this app started is stopped (a Queen started elsewhere keeps running for the other sessions).
    func stopIfOurs() {
        if startedPid > 0 { kill(pid_t(startedPid), SIGTERM) }
    }

    // ---------------------------------------------------------------- chats
    @MainActor
    func loadChats() async {
        guard let j = await json("/api/chats"), let list = j["chats"] as? [[String: Any]] else { return }
        chats = list.compactMap { c -> ChatMeta? in
            guard let id = c["id"] as? String else { return nil }
            return ChatMeta(id: id, title: (c["title"] as? String) ?? "Untitled",
                            count: (c["message_count"] as? Int) ?? 0, updated: (c["updated_at"] as? String) ?? "")
        }
    }

    @MainActor
    func open(_ id: String) async {
        guard !busy, let j = await json("/api/chats/" + id), let c = j["chat"] as? [String: Any] else { return }
        let ms = (c["messages"] as? [[String: Any]]) ?? []
        chatId = id
        messages = ms.compactMap { m -> Msg? in
            guard let r = m["role"] as? String, r == "user" || r == "assistant" else { return nil }
            return Msg(role: r, content: Queen.visible((m["content"] as? String) ?? ""))
        }
    }

    @MainActor
    func newChat() {
        guard !busy else { return }
        chatId = Queen.newId()
        messages = []
    }

    /// The model's hidden thinking is not shown.
    static func visible(_ s: String) -> String {
        var t = s
        while let a = t.range(of: "<think>") {
            if let b = t.range(of: "</think>", range: a.upperBound..<t.endIndex) {
                t.removeSubrange(a.lowerBound..<b.upperBound)
            } else {
                t.removeSubrange(a.lowerBound..<t.endIndex)
            }
        }
        return t.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    // ---------------------------------------------------------------- one turn
    @MainActor
    func send(_ text: String) {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !t.isEmpty, !busy else { return }
        messages.append(Msg(role: "user", content: t))
        messages.append(Msg(role: "assistant", content: ""))
        busy = true
        let history = messages.dropLast().map { ["role": $0.role, "content": $0.content] }
        task = Task { @MainActor in
            await self.stream(history: Array(history))
            self.busy = false
            await self.save()
            await self.loadChats()
            await self.refresh()
        }
    }

    @MainActor
    func stop() {
        task?.cancel()
        busy = false
    }

    @MainActor
    private func appendToReply(_ s: String) {
        guard !messages.isEmpty else { return }
        messages[messages.count - 1].content += s
    }

    @MainActor
    private func stream(history: [[String: String]]) async {
        guard let r = request("/api/chat", body: ["messages": history], timeout: 900) else { return }
        var raw = ""
        do {
            let (bytes, resp) = try await URLSession.shared.bytes(for: r)
            if let h = resp as? HTTPURLResponse, h.statusCode >= 400 {
                var body = ""
                for try await l in bytes.lines { body += l }
                let err = (try? JSONSerialization.jsonObject(with: Data(body.utf8)) as? [String: Any])?["error"] as? String
                appendToReply("Queen answered \(h.statusCode): " + (err ?? body.prefix(300).description))
                return
            }
            for try await l in bytes.lines {
                if Task.isCancelled { break }
                guard let o = try? JSONSerialization.jsonObject(with: Data(l.utf8)) as? [String: Any] else { continue }
                if let tok = o["t"] as? String {
                    raw += tok
                    messages[messages.count - 1].content = Queen.visible(raw)
                }
                if let e = o["error"] { appendToReply("\nERROR: \(e)") }
            }
        } catch {
            if !Task.isCancelled { appendToReply("\n(no answer: \(error.localizedDescription))") }
        }
        if Task.isCancelled { appendToReply("\n(stopped)") }
    }

    @MainActor
    private func save() async {
        let ms = messages.map { ["role": $0.role, "content": $0.content] }
        _ = await json("/api/chats/save", body: ["id": chatId, "title": "", "messages": ms])
    }
}
