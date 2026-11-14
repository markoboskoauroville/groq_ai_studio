# whatsapp-lessons

What Claude corrected in Queen's WhatsApp plans (POST /api/whatsapp/supervised). Read before planning: the same request is
planned the corrected way.

- 14.11.2026: For "show my latest messages" plan `chats` to list the recent chats; use `shot` only when Marko asks for a picture or screenshot of the screen. (Marko: "show my latest messages"; Queen {"action": "shot"} -> Claude {"action": "chats"})
- 14.11.2026: When Marko asks to see the last or latest messages from a named person, plan `read {chat, n}` for that chat; use `shot` only when he explicitly asks for a picture or screenshot. (Marko: "show me the last messages from Svemir"; Queen {"action": "shot"} -> Claude {"action": "read", "chat": "Svemir", "n": 5})
- 14.11.2026: Plan from the intended meaning even when the request has typos or split words, and 'show my latest messages' always maps to `chats`, never to no plan. (Marko: "showm y latestm essages"; Queen had no plan -> Claude {"action": "chats"})
