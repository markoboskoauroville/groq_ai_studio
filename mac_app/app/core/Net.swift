// Net.swift: a small HTTP/1.1 server and client on Darwin sockets (Phase A, 14.11.2026). No dependency.
// Why plain BSD sockets and not NWListener: Queen must own 127.0.0.1:8765 exactly like waitress did (SO_REUSEADDR only,
// so a restart is not blocked by TIME_WAIT, and never SO_REUSEPORT, so two Queens can never share the port), and a
// proxy must pipe raw bytes. One thread per connection, `Connection: close` on every answer, streams are chunked.
import Foundation
import Darwin

// ---------------------------------------------------------------- socket
final class Sock {
    let fd: Int32
    private var pending = [UInt8]()
    private(set) var dead = false

    init(fd: Int32) {
        self.fd = fd
        var one: Int32 = 1
        setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &one, socklen_t(MemoryLayout<Int32>.size))
    }

    /// Read timeout in seconds (0 = none).
    func setTimeout(_ seconds: Double) {
        var tv = timeval(tv_sec: Int(seconds), tv_usec: Int32((seconds - Double(Int(seconds))) * 1_000_000))
        setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, socklen_t(MemoryLayout<timeval>.size))
    }

    /// Some bytes, or nil when the other side closed (or the read timed out / failed).
    func readSome(max: Int = 65536) -> [UInt8]? {
        if !pending.isEmpty {
            let out = pending
            pending.removeAll()
            return out
        }
        var buf = [UInt8](repeating: 0, count: max)
        while true {
            let n = buf.withUnsafeMutableBytes { Darwin.recv(fd, $0.baseAddress, max, 0) }
            if n > 0 { return Array(buf[0..<n]) }
            if n < 0 && errno == EINTR { continue }
            return nil
        }
    }

    /// Bytes up to and including the first CRLFCRLF (the head of a request or response).
    func readHead(limit: Int = 256 * 1024) -> [UInt8]? {
        var acc = [UInt8]()
        while true {
            if let r = Sock.find([13, 10, 13, 10], in: acc) {
                let end = r + 4
                if end < acc.count { pending = Array(acc[end...]) + pending }
                return Array(acc[0..<end])
            }
            if acc.count > limit { return nil }
            guard let more = readSome() else { return nil }
            acc += more
        }
    }

    func readExact(_ n: Int) -> [UInt8]? {
        var acc = [UInt8]()
        while acc.count < n {
            guard let more = readSome(max: min(65536, max(1, n - acc.count))) else { return nil }
            acc += more
        }
        if acc.count > n {
            pending = Array(acc[n...]) + pending
            acc = Array(acc[0..<n])
        }
        return acc
    }

    func readLine(limit: Int = 64 * 1024) -> String? {
        var acc = [UInt8]()
        while true {
            if let i = acc.firstIndex(of: 10) {
                if i + 1 < acc.count { pending = Array(acc[(i + 1)...]) + pending }
                var line = Array(acc[0..<i])
                if line.last == 13 { line.removeLast() }
                return String(decoding: line, as: UTF8.self)
            }
            if acc.count > limit { return nil }
            guard let more = readSome() else {
                return acc.isEmpty ? nil : String(decoding: acc, as: UTF8.self)
            }
            acc += more
        }
    }

    func readToEnd() -> [UInt8] {
        var acc = [UInt8]()
        while let more = readSome() { acc += more }
        return acc
    }

    @discardableResult
    func write(_ bytes: [UInt8]) -> Bool {
        if dead { return false }
        var off = 0
        while off < bytes.count {
            let n = bytes.withUnsafeBytes { Darwin.send(fd, $0.baseAddress! + off, bytes.count - off, 0) }
            if n < 0 && errno == EINTR { continue }
            if n <= 0 { dead = true; return false }
            off += n
        }
        return true
    }

    @discardableResult
    func write(_ s: String) -> Bool { write(Array(s.utf8)) }

    @discardableResult
    func write(_ d: Data) -> Bool { write([UInt8](d)) }

    func shut() {
        Darwin.shutdown(fd, SHUT_RDWR)
        Darwin.close(fd)
        dead = true
    }

    static func find(_ needle: [UInt8], in hay: [UInt8]) -> Int? {
        guard hay.count >= needle.count else { return nil }
        var i = 0
        while i <= hay.count - needle.count {
            if hay[i] == needle[0] {
                var ok = true
                for j in 1..<needle.count where hay[i + j] != needle[j] { ok = false; break }
                if ok { return i }
            }
            i += 1
        }
        return nil
    }

    /// A connection to 127.0.0.1:port, or nil (nothing listens there).
    static func open(port: UInt16, timeout: Double = 30) -> Sock? {
        let fd = Darwin.socket(AF_INET, SOCK_STREAM, 0)
        if fd < 0 { return nil }
        var addr = Sock.loopback(port)
        let r = withUnsafePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.connect(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        if r != 0 { Darwin.close(fd); return nil }
        let s = Sock(fd: fd)
        s.setTimeout(timeout)
        return s
    }

    static func loopback(_ port: UInt16) -> sockaddr_in {
        var addr = sockaddr_in()
        addr.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = in_port_t(port).bigEndian
        addr.sin_addr.s_addr = inet_addr("127.0.0.1")
        return addr
    }
}

// ---------------------------------------------------------------- request
struct HTTPRequest {
    var method = "GET"
    var target = "/"
    var path = "/"
    var version = "HTTP/1.1"
    var query: [String: String] = [:]
    var headers: [(String, String)] = []
    var body = Data()

    func header(_ name: String) -> String? {
        let n = name.lowercased()
        return headers.first { $0.0.lowercased() == n }?.1
    }

    /// Like Flask's get_json(silent=True) or {}: a JSON object, else empty.
    var json: [String: Any] {
        guard !body.isEmpty, let o = try? JSONSerialization.jsonObject(with: body) as? [String: Any] else { return [:] }
        return o
    }

    static func decodeQuery(_ q: String) -> [String: String] {
        var out: [String: String] = [:]
        for part in q.split(separator: "&", omittingEmptySubsequences: true) {
            let kv = part.split(separator: "=", maxSplits: 1, omittingEmptySubsequences: false)
            func dec(_ s: Substring) -> String {
                let t = s.replacingOccurrences(of: "+", with: " ")
                return t.removingPercentEncoding ?? t
            }
            let k = dec(kv[0])
            if out[k] == nil { out[k] = kv.count > 1 ? dec(kv[1]) : "" }
        }
        return out
    }

    /// Reads one request from a client: head, `Expect: 100-continue`, Content-Length or chunked body.
    static func read(from s: Sock) -> HTTPRequest? {
        guard let head = s.readHead() else { return nil }
        let text = String(decoding: head, as: UTF8.self)
        var lines = text.components(separatedBy: "\r\n")
        guard !lines.isEmpty else { return nil }
        let first = lines.removeFirst().split(separator: " ", omittingEmptySubsequences: true)
        guard first.count >= 2 else { return nil }
        var r = HTTPRequest()
        r.method = String(first[0]).uppercased()
        r.target = String(first[1])
        r.version = first.count > 2 ? String(first[2]) : "HTTP/1.0"
        for l in lines where !l.isEmpty {
            guard let c = l.firstIndex(of: ":") else { continue }
            let k = String(l[l.startIndex..<c]).trimmingCharacters(in: .whitespaces)
            let v = String(l[l.index(after: c)...]).trimmingCharacters(in: .whitespaces)
            r.headers.append((k, v))
        }
        if let q = r.target.firstIndex(of: "?") {
            r.path = String(r.target[r.target.startIndex..<q])
            r.query = decodeQuery(String(r.target[r.target.index(after: q)...]))
        } else {
            r.path = r.target
        }
        if let p = r.path.removingPercentEncoding { r.path = p }
        if (r.header("Expect") ?? "").lowercased() == "100-continue" {
            s.write("HTTP/1.1 100 Continue\r\n\r\n")
        }
        if (r.header("Transfer-Encoding") ?? "").lowercased().contains("chunked") {
            var body = [UInt8]()
            while true {
                guard let sizeLine = s.readLine() else { return nil }
                let hex = sizeLine.split(separator: ";").first.map(String.init)?.trimmingCharacters(in: .whitespaces) ?? ""
                guard let n = Int(hex, radix: 16) else { return nil }
                if n == 0 {
                    while let t = s.readLine(), !t.isEmpty {}   // trailers
                    break
                }
                guard let chunk = s.readExact(n) else { return nil }
                body += chunk
                _ = s.readLine()
            }
            r.body = Data(body)
        } else if let cl = r.header("Content-Length"), let n = Int(cl.trimmingCharacters(in: .whitespaces)), n > 0 {
            guard let b = s.readExact(n) else { return nil }
            r.body = Data(b)
        }
        return r
    }
}

// ---------------------------------------------------------------- response
let HTTP_REASONS: [Int: String] = [
    200: "OK", 201: "Created", 204: "No Content", 400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
    404: "Not Found", 405: "Method Not Allowed", 409: "Conflict", 422: "Unprocessable Entity", 429: "Too Many Requests",
    500: "Internal Server Error", 502: "Bad Gateway", 503: "Service Unavailable", 504: "Gateway Timeout",
]

/// JSON text the way Queen's clients expect it (sorted keys like Flask's jsonify). Never throws: an object that
/// JSONSerialization cannot write becomes an error object instead of an exception.
func jsonBytes(_ o: Any) -> Data {
    let obj: Any = JSONSerialization.isValidJSONObject(o) ? o : ["ok": false, "error": "internal: answer is not JSON"]
    return (try? JSONSerialization.data(withJSONObject: obj, options: [.sortedKeys, .withoutEscapingSlashes])) ?? Data("{}".utf8)
}

func jsonLine(_ o: [String: Any]) -> Data {
    var d = jsonBytes(o)
    d.append(10)
    return d
}

final class Responder {
    let sock: Sock
    let http10: Bool
    private var streaming = false
    private(set) var sent = false

    init(_ s: Sock, http10: Bool) {
        sock = s
        self.http10 = http10
    }

    var alive: Bool { !sock.dead }

    func send(_ status: Int, _ type: String, _ body: Data, headers: [(String, String)] = []) {
        guard !sent else { return }
        sent = true
        var h = "HTTP/1.1 \(status) \(HTTP_REASONS[status] ?? "Status")\r\nContent-Type: \(type)\r\n"
        h += "Content-Length: \(body.count)\r\nConnection: close\r\nServer: queen-swift\r\n"
        for (k, v) in headers { h += "\(k): \(v)\r\n" }
        h += "\r\n"
        sock.write(h)
        sock.write(body)
    }

    func json(_ status: Int, _ o: Any) { send(status, "application/json", jsonBytes(o)) }
    func json(_ o: Any) { json(200, o) }
    func text(_ status: Int, _ s: String) { send(status, "text/plain; charset=utf-8", Data(s.utf8)) }

    /// Starts a streamed answer (chunked; an HTTP/1.0 client gets a body that ends when the connection closes).
    func begin(_ status: Int, _ type: String, headers: [(String, String)] = []) {
        guard !sent else { return }
        sent = true
        streaming = true
        var h = "HTTP/1.1 \(status) \(HTTP_REASONS[status] ?? "Status")\r\nContent-Type: \(type)\r\n"
        if !http10 { h += "Transfer-Encoding: chunked\r\n" }
        h += "Connection: close\r\nServer: queen-swift\r\n"
        for (k, v) in headers { h += "\(k): \(v)\r\n" }
        h += "\r\n"
        sock.write(h)
    }

    @discardableResult
    func chunk(_ d: Data) -> Bool {
        guard streaming, !d.isEmpty else { return alive }
        if http10 { return sock.write(d) }
        var b = Array(String(d.count, radix: 16).utf8) + [13, 10]
        b += [UInt8](d)
        b += [13, 10]
        return sock.write(b)
    }

    @discardableResult
    func chunk(_ s: String) -> Bool { chunk(Data(s.utf8)) }

    func end() {
        if streaming && !http10 { sock.write("0\r\n\r\n") }
        streaming = false
    }
}

// ---------------------------------------------------------------- server
enum ServerError: Error, CustomStringConvertible {
    case bind(Int32)
    case socket
    var description: String {
        switch self {
        case .bind(let e): return "bind failed: \(String(cString: strerror(e)))"
        case .socket: return "socket() failed"
        }
    }
    var inUse: Bool { if case .bind(let e) = self { return e == EADDRINUSE }; return false }
}

final class HTTPServer {
    typealias Handler = (HTTPRequest, Responder) -> Void
    private let handler: Handler
    /// Raw handlers get the client socket (the proxy pipes bytes); return true when the request was taken.
    var raw: ((HTTPRequest, Sock) -> Bool)?
    private var fd: Int32 = -1
    private(set) var port: UInt16 = 0

    init(_ handler: @escaping Handler) {
        self.handler = handler
        signal(SIGPIPE, SIG_IGN)
    }

    /// Binds 127.0.0.1:port (0 = any free port) and serves on its own thread. Returns the port.
    @discardableResult
    func start(port: UInt16) throws -> UInt16 {
        let fd = Darwin.socket(AF_INET, SOCK_STREAM, 0)
        if fd < 0 { throw ServerError.socket }
        var one: Int32 = 1
        setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, socklen_t(MemoryLayout<Int32>.size))
        var addr = Sock.loopback(port)
        let r = withUnsafePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { Darwin.bind(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) }
        }
        if r != 0 {
            let e = errno
            Darwin.close(fd)
            throw ServerError.bind(e)
        }
        if Darwin.listen(fd, 128) != 0 {
            let e = errno
            Darwin.close(fd)
            throw ServerError.bind(e)
        }
        var bound = sockaddr_in()
        var len = socklen_t(MemoryLayout<sockaddr_in>.size)
        _ = withUnsafeMutablePointer(to: &bound) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { getsockname(fd, $0, &len) }
        }
        self.fd = fd
        self.port = UInt16(bigEndian: bound.sin_port)
        let t = Thread { [weak self] in self?.acceptLoop(fd) }
        t.name = "queen-accept-\(self.port)"
        t.start()
        return self.port
    }

    func stop() {
        if fd >= 0 {
            Darwin.shutdown(fd, SHUT_RDWR)
            Darwin.close(fd)
            fd = -1
        }
    }

    private func acceptLoop(_ lfd: Int32) {
        while true {
            let c = Darwin.accept(lfd, nil, nil)
            if c < 0 {
                if errno == EINTR || errno == ECONNABORTED { continue }
                return
            }
            let t = Thread { [weak self] in self?.serve(Sock(fd: c)) }
            t.stackSize = 1 << 20
            t.start()
        }
    }

    private func serve(_ s: Sock) {
        s.setTimeout(60)        // a client that sends nothing for a minute is gone
        guard let req = HTTPRequest.read(from: s) else { s.shut(); return }
        s.setTimeout(0)
        if let raw = raw, raw(req, s) { s.shut(); return }
        let res = Responder(s, http10: req.version == "HTTP/1.0")
        handler(req, res)
        if !res.sent { res.json(500, ["ok": false, "error": "no answer"]) }
        res.end()
        s.shut()
    }
}

// ---------------------------------------------------------------- client (to 127.0.0.1 only: the backend, tests)
struct LocalResponse {
    var status: Int
    var headers: [String: String]
    var body: Data
    var json: [String: Any] { (try? JSONSerialization.jsonObject(with: body) as? [String: Any]) ?? [:] }
}

enum LocalHTTP {
    /// One request to 127.0.0.1:port, HTTP/1.0 so the answer is never chunked. nil = nothing listens there.
    static func call(port: UInt16, method: String, path: String, body: Data? = nil, headers: [(String, String)] = [],
                     timeout: Double = 30) -> LocalResponse? {
        guard let s = Sock.open(port: port, timeout: timeout) else { return nil }
        defer { s.shut() }
        var h = "\(method) \(path) HTTP/1.0\r\nHost: 127.0.0.1:\(port)\r\nConnection: close\r\n"
        for (k, v) in headers { h += "\(k): \(v)\r\n" }
        if let b = body {
            if !headers.contains(where: { $0.0.lowercased() == "content-type" }) { h += "Content-Type: application/json\r\n" }
            h += "Content-Length: \(b.count)\r\n"
        }
        h += "\r\n"
        guard s.write(h) else { return nil }
        if let b = body, !b.isEmpty, !s.write(b) { return nil }
        return readResponse(s)
    }

    static func readResponse(_ s: Sock) -> LocalResponse? {
        guard let head = readHead(s) else { return nil }
        let rest = s.readToEnd()
        var body = rest
        if (head.1["transfer-encoding"] ?? "").lowercased().contains("chunked") { body = dechunk(rest) }
        return LocalResponse(status: head.0, headers: head.1, body: Data(body))
    }

    static func readHead(_ s: Sock) -> (Int, [String: String])? {
        guard let head = s.readHead() else { return nil }
        let lines = String(decoding: head, as: UTF8.self).components(separatedBy: "\r\n")
        let first = lines.first?.split(separator: " ") ?? []
        guard first.count >= 2, let status = Int(first[1]) else { return nil }
        var hs: [String: String] = [:]
        for l in lines.dropFirst() {
            guard let c = l.firstIndex(of: ":") else { continue }
            hs[l[l.startIndex..<c].lowercased()] = String(l[l.index(after: c)...]).trimmingCharacters(in: .whitespaces)
        }
        return (status, hs)
    }

    static func dechunk(_ b: [UInt8]) -> [UInt8] {
        var out = [UInt8]()
        var i = 0
        while i < b.count {
            guard let nl = b[i...].firstIndex(of: 10) else { break }
            let line = String(decoding: b[i..<nl], as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
            let hex = line.split(separator: ";").first.map(String.init) ?? ""
            guard let n = Int(hex, radix: 16), n > 0 else { break }
            let start = nl + 1
            let end = min(b.count, start + n)
            out += b[start..<end]
            i = end + 2
        }
        return out
    }
}
