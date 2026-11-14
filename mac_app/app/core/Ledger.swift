// Ledger.swift: what Queen spent, a port of MODEL_PRICING / get_model_rates / record_spend (Phase A, 14.11.2026).
// The same file ~/.groq/spend_ledger.json and the same fields; after a paid call the Cost Agent hears it (POST /spent,
// as cost_gate.report does: port from ~/.config/mantra-ports.json "costagent", default 9047, or the VM's remote url).
import Foundation

let MODEL_PRICING: [String: (Double, Double)] = [
    "qwen/qwen3.8-27b": (0.80, 4.00),
    "qwen/qwen3.6-27b": (0.80, 4.00),
    "qwen/qwen3-32b": (0.29, 0.59),
    "qwen-qwq-32b": (0.29, 0.39),
    "openai/gpt-oss-120b": (0.15, 0.60),
    "openai/gpt-oss-20b": (0.075, 0.30),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "meta-llama/llama-4-maverick-17b-128e-instruct": (0.20, 0.60),
    "meta-llama/llama-4-scout-17b-16e-instruct": (0.11, 0.34),
    "deepseek-r1-distill-llama-70b": (0.75, 0.99),
    "moonshotai/kimi-k2-instruct": (1.00, 3.00),
    "moonshotai/kimi-k2-instruct-0905": (1.00, 3.00),
    "gemma2-9b-it": (0.20, 0.20),
    "allam-2-7b": (0.20, 0.20),
    "meta-llama/llama-prompt-guard-2-86m": (0.04, 0.04),
    "meta-llama/llama-prompt-guard-2-22m": (0.03, 0.03),
    "canopylabs/orpheus-v1-english": (0.20, 0.20),
    "default": (0.50, 1.50),
]

let DEFAULT_MODEL = "qwen/qwen3.6-27b"
let FALLBACK_MODELS = [DEFAULT_MODEL, "openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b"]

final class Ledger {
    private let cfg: QueenConfig
    private let lock = NSLock()
    var livePricing: [String: (Double, Double)] = [:]

    init(_ cfg: QueenConfig) { self.cfg = cfg }

    private var file: String { cfg.groqDir + "/spend_ledger.json" }

    func rates(_ model: String) -> (Double, Double) {
        if let r = livePricing[model] { return r }
        if let r = MODEL_PRICING[model] { return r }
        let low = model.lowercased()
        if low.contains("8b") || low.contains("scout") { return (0.08, 0.20) }
        if low.contains("70b") { return (0.59, 0.79) }
        if low.contains("qwen3") && low.contains("32b") { return (0.29, 0.59) }
        return MODEL_PRICING["default"]!
    }

    static func pricingJSON(_ p: [String: (Double, Double)]) -> [String: Any] {
        var o: [String: Any] = [:]
        for (k, v) in p { o[k] = [v.0, v.1] }
        return o
    }

    var mergedPricing: [String: Any] {
        var m = MODEL_PRICING
        for (k, v) in livePricing { m[k] = v }
        return Ledger.pricingJSON(m)
    }

    func cost(_ model: String, _ pt: Int, _ ct: Int) -> [String: Double] {
        let r = rates(model)
        let p = Double(pt) * r.0 / 1_000_000.0
        let c = Double(ct) * r.1 / 1_000_000.0
        return ["prompt_cost": p, "completion_cost": c, "total_cost": p + c, "rate_in": r.0, "rate_out": r.1]
    }

    func load() -> [String: Any] {
        if let d = Files.readJSON(file) as? [String: Any] { return d }
        return ["total_spent": 0.0, "total_prompt_tokens": 0, "total_completion_tokens": 0, "total_tokens": 0,
                "prompts_count": 0, "history": [Any]()]
    }

    static func num(_ o: Any?) -> Double { (o as? NSNumber)?.doubleValue ?? 0 }
    static func int(_ o: Any?) -> Int { (o as? NSNumber)?.intValue ?? 0 }

    var totalSpent: Double { Ledger.num(load()["total_spent"]) }

    /// record_spend: adds the call to the ledger (history: the last 100) and tells the Cost Agent. Returns (cost, ledger).
    @discardableResult
    func record(_ model: String, _ pt: Int, _ ct: Int, reqId: String = "") -> ([String: Double], [String: Any]) {
        lock.lock(); defer { lock.unlock() }
        let ci = cost(model, pt, ct)
        var l = load()
        l["total_spent"] = pyRound(Ledger.num(l["total_spent"]) + ci["total_cost"]!, 6)
        l["total_prompt_tokens"] = Ledger.int(l["total_prompt_tokens"]) + pt
        l["total_completion_tokens"] = Ledger.int(l["total_completion_tokens"]) + ct
        l["total_tokens"] = Ledger.int(l["total_prompt_tokens"]) + Ledger.int(l["total_completion_tokens"])
        l["prompts_count"] = Ledger.int(l["prompts_count"]) + 1
        var h = (l["history"] as? [Any]) ?? []
        h.append(["timestamp": Clock.now, "time_str": Clock.stamp, "model": model, "prompt_tokens": pt,
                  "completion_tokens": ct, "total_tokens": pt + ct, "cost": ci["total_cost"]!, "req_id": reqId] as [String: Any])
        l["history"] = Array(h.suffix(100))
        _ = Files.writeJSON(file, l, pretty: true, privateFile: true)
        if cfg.reportCost { report(ci["total_cost"]!, ref: reqId, what: model) }
        return (ci, l)
    }

    /// cost_gate.report: never blocks, never raises.
    func report(_ usd: Double, ref: String, what: String) {
        let base = cfg.userHome + "/.config/cost-agent"
        let remoteURL = Files.read(base + "/url")?.trimmingCharacters(in: .whitespacesAndNewlines)
        let token = Files.read(base + "/token")?.trimmingCharacters(in: .whitespacesAndNewlines)
        var url: String
        if let r = remoteURL, !r.isEmpty {
            url = r
        } else {
            var port = 9047
            if let ports = Files.readJSON(cfg.userHome + "/.config/mantra-ports.json") as? [String: Any],
               let ca = ports["costagent"] as? [String: Any], let p = ca["port"] as? NSNumber { port = p.intValue }
            url = "http://127.0.0.1:\(port)"
        }
        guard let u = URL(string: url + "/spent") else { return }
        var r = URLRequest(url: u, timeoutInterval: 5)
        r.httpMethod = "POST"
        r.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let t = token, remoteURL != nil, !(remoteURL ?? "").isEmpty { r.setValue(t, forHTTPHeaderField: "X-Cost-Token") }
        let body: [String: Any] = ["who": "queen", "provider": "groq", "usd": usd, "ref": ref, "what": what, "job": NSNull(),
                                   "where": (remoteURL ?? "").isEmpty ? "mac" : "vm"]
        r.httpBody = jsonBytes(body)
        URLSession.shared.dataTask(with: r) { _, _, _ in }.resume()
    }
}
