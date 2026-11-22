// Studio.swift (v35, 22.11.2026, audit round 2): Queen's window drawn OFF SCREEN, never on Marko's screen.
// MANTRA_MANIFEST screenshots-without-his-screen: "prefer an off-screen render built into the app".
//
//   open -n -g -j /Applications/Queen.app --args --studio-shot /path/shot.png --width 820 [--height 700]
//
// A second, hidden Queen (accessory, never activated) that does NOT start a server, a backend or the updater: it reads
// the running Queen on 127.0.0.1:8765 (read only), draws the real window into a PNG at the given width and writes the
// Accessibility tree of that window next to it (<png>.ax.json: every element's role, label, identifier, value), then
// exits with exit(), so no quit guard and no applicationWillTerminate (which would stop the running Queen's backend).
import SwiftUI
import AppKit

enum Studio {
    static var args: [String] { CommandLine.arguments }
    static var active: Bool { args.contains("--studio-shot") }

    static func value(_ flag: String) -> String? {
        guard let i = args.firstIndex(of: flag), i + 1 < args.count else { return nil }
        return args[i + 1]
    }

    /// Called from applicationDidFinishLaunching instead of the normal start.
    static func run() {
        NSApp.setActivationPolicy(.accessory)
        let path = value("--studio-shot") ?? "/tmp/queen-studio.png"
        let width = CGFloat(Double(value("--width") ?? "") ?? 920)
        let height = CGFloat(Double(value("--height") ?? "") ?? 700)
        hideSceneWindows()
        Task { @MainActor in await Queen.shared.refresh() }
        let host = NSHostingView(rootView: Root().frame(width: width, height: height))
        host.frame = NSRect(x: 0, y: 0, width: width, height: height)
        let w = NSWindow(contentRect: NSRect(x: -30000, y: -30000, width: width, height: height),
                         styleMask: [.borderless], backing: .buffered, defer: false)
        w.contentView = host
        w.isReleasedWhenClosed = false
        w.orderBack(nil)                       // never ordered front, never key, far off every screen
        var ticks = 0
        Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { t in
            ticks += 1
            hideSceneWindows()
            // wait for the data (credit, chats) from the running Queen, at most 12 s
            let ready = Capi.shared.creditLoaded && !Capi.shared.convs.isEmpty
            guard ready || ticks >= 24 else { return }
            t.invalidate()
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                host.layoutSubtreeIfNeeded()
                if let rep = host.bitmapImageRepForCachingDisplay(in: host.bounds) {
                    host.cacheDisplay(in: host.bounds, to: rep)
                    if let png = rep.representation(using: .png, properties: [:]) {
                        try? png.write(to: URL(fileURLWithPath: path))
                    }
                }
                var nodes: [[String: Any]] = []
                walk(host, depth: 0, into: &nodes)
                let out: [String: Any] = ["width": width, "height": height, "version": VERSION, "ready": ready, "nodes": nodes]
                if let data = try? JSONSerialization.data(withJSONObject: out, options: [.prettyPrinted, .sortedKeys]) {
                    try? data.write(to: URL(fileURLWithPath: path + ".ax.json"))
                }
                print("studio-shot written: \(path) (+ .ax.json, \(nodes.count) elements, data ready: \(ready))")
                exit(0)
            }
        }
    }

    /// The SwiftUI scene opens its own main window at launch: in studio mode it is ordered out at once (the app is also
    /// launched hidden with open -j), so nothing appears on Marko's screen.
    static func hideSceneWindows() {
        for w in NSApp.windows where w.frame.origin.x > -20000 { w.orderOut(nil) }
    }

    /// The legacy attribute API on NSObject works for NSView, NSAccessibilityElement and SwiftUI's private nodes alike.
    static func walk(_ e: Any, depth: Int, into nodes: inout [[String: Any]]) {
        guard depth < 60, nodes.count < 3000, let o = e as? NSObject else { return }
        func attr(_ a: NSAccessibility.Attribute) -> Any? { o.accessibilityAttributeValue(a) }
        var n: [String: Any] = ["depth": depth]
        if let r = attr(.role) as? String { n["role"] = r }
        if let l = attr(.description) as? String, !l.isEmpty { n["label"] = l }
        if let t = attr(.title) as? String, !t.isEmpty { n["title"] = t }
        if let i = attr(.identifier) as? String, !i.isEmpty { n["id"] = i }
        if let v = attr(.value) { n["value"] = "\(v)" }
        if n.count > 1 { nodes.append(n) }
        for c in (attr(.children) as? [Any]) ?? [] { walk(c, depth: depth + 1, into: &nodes) }
    }
}
