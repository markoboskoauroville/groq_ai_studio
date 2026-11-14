// Prompt.swift: Queen's system prompt, built exactly like app.py build_queen_system_prompt() (Phase A, 14.11.2026).
// The text is not copied by hand. The helper gen_prompt.py (in the bundle, stdlib only) reads the installed
// ~/.groq/qwen_app/app.py with ast and gives a template with three markers; it runs again whenever app.py changes.
// Every turn the markers get: the version ("v<version.json>"), where she runs, and EVERY ~/.groq/queen_skills/*.md
// (sorted, "### skill: <stem>"), like _queen_skills_block(). A CI test compares the result to Python's byte for byte.
import Foundation

let MARK_VERSION = "\u{E000}VERSION\u{E000}"
let MARK_WHERE = "\u{E000}WHERE\u{E000}"
let MARK_SKILLS = "\u{E000}SKILLS\u{E000}"

final class PromptBuilder {
    private let cfg: QueenConfig
    private let lock = NSLock()
    private var template: [String: String]?
    private var templateMtime: Double = -1
    private(set) var source = "none"

    init(_ cfg: QueenConfig) { self.cfg = cfg }

    static func parse(_ d: Data) -> [String: String]? {
        guard let o = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
              let t = o["template"] as? String, let wm = o["where_mac"] as? String, let wo = o["where_other"] as? String,
              t.contains(MARK_VERSION), t.contains(MARK_WHERE), t.contains(MARK_SKILLS) else { return nil }
        return ["template": t, "where_mac": wm, "where_other": wo]
    }

    /// The template: from the live app.py through the helper (cached by mtime), else the copy in the bundle.
    func currentTemplate() -> [String: String]? {
        lock.lock(); defer { lock.unlock() }
        let app = cfg.sourceAppPy
        let m = Files.mtime(app)
        if template != nil && m == templateMtime { return template }
        if m > 0, let helper = cfg.promptHelper, FileManager.default.fileExists(atPath: helper) {
            let r = runProcess(cfg.pythonExe, ["-I", helper, app], timeout: 30)
            if r.code == 0, let t = PromptBuilder.parse(Data(r.out.utf8)) {
                template = t
                templateMtime = m
                source = "live app.py"
                return t
            }
        }
        if template == nil, let b = cfg.bundledPrompt, let d = FileManager.default.contents(atPath: b), let t = PromptBuilder.parse(d) {
            template = t
            templateMtime = m
            source = "bundle"
        }
        return template
    }

    /// _queen_skills_block(): every skill file, every turn.
    func skillsBlock() -> String {
        let fm = FileManager.default
        guard let names = try? fm.contentsOfDirectory(atPath: cfg.skills) else { return "" }
        let md = names.filter { $0.hasSuffix(".md") }.sorted { a, b in
            a.unicodeScalars.lexicographicallyPrecedes(b.unicodeScalars) { x, y in x.value < y.value }
        }
        if md.isEmpty { return "" }
        var parts = ["\n\nYOUR SKILLS (written for you so you can do these without Claude Code; follow them):\n"]
        for n in md {
            guard let text = Files.read(cfg.skills + "/" + n) else { continue }
            let stem = String(n.dropLast(3))
            parts.append("\n### skill: \(stem)\n\(text.trimmingCharacters(in: .whitespacesAndNewlines))\n")
        }
        return parts.joined()
    }

    /// The version she says she runs: "v" + version.json's number (VERSION in app.py).
    func version() -> String {
        if let o = Files.readJSON(cfg.versionFile) as? [String: Any], let v = o["version"] as? NSNumber { return "v\(v.intValue)" }
        return "v1"
    }

    func build(persona: String = "") -> String? {
        guard let t = currentTemplate() else { return nil }
        let whereText = cfg.location == "mac" ? t["where_mac"]! : t["where_other"]!
        var base = t["template"]!
            .replacingOccurrences(of: MARK_VERSION, with: version())
            .replacingOccurrences(of: MARK_WHERE, with: whereText)
        base = base.replacingOccurrences(of: MARK_SKILLS, with: skillsBlock())
        if !persona.isEmpty { return "\(base)\nAdditional Persona / Instructions:\n\(persona)" }
        return base
    }
}

/// detect_code_intent(): does the prompt ask for the answer in a code box?
func detectCodeIntent(_ text: String) -> Bool {
    if text.isEmpty { return false }
    let lower = text.lowercased()
    let patterns = [
        #"\b(in\s+(the\s+|a\s+)?code\s*box)\b"#,
        #"\b(write\s+(answer\s+|it\s+|response\s+)?in\s+(the\s+|a\s+)?code\s*box)\b"#,
        #"\b(put\s+(it\s+|answer\s+)?in\s+(the\s+|a\s+)?code\s*box)\b"#,
        #"\b(code\s*box\s+format|code\s*box\s+mode)\b"#,
        #"\b(only\s+code|code\s+only|just\s+the\s+code)\b"#,
        #"\b(as\s+a\s+code\s*block|in\s+a\s+code\s*block)\b"#,
        #"\b(provide\s+only\s+(the\s+)?code)\b"#,
        #"\b(pure\s+code\s+without\s+explanation)\b"#,
    ]
    let ns = lower as NSString
    for p in patterns {
        if let re = try? NSRegularExpression(pattern: p),
           re.firstMatch(in: lower, range: NSRange(location: 0, length: ns.length)) != nil { return true }
    }
    return false
}
