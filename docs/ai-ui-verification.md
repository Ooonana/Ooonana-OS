# Native AI UI verification

Design reference: [Ooonana AI concept](assets/ooonana-ai-concept.png). Current [rendered native interface](assets/ooonana-ai-chat.png) implements GTK3, not a web page. Browser rendering cannot exercise GTK windows; isolated Xvfb screenshots and GTK interaction tests are used instead.

Tokens: opaque graphite `#101317`, sidebar `#171b21`, surfaces `#1b1f26`, user bubble `#272c34`, border `#343b46`, text `#f5f5f7`, orange `#ffb21a`. Compact chrome follows existing 10.5pt GTK typography; wide screens use 14.5pt content. Layout uses one sidebar, open conversation area, message bubbles, and one composer. No raster screenshot is shipped as interactive UI.

Comparison ledger, directly inspected with image viewer:

| Point | Reference and implementation | Result |
| --- | --- | --- |
| Information architecture | New chat, Search chats, Recent; Offline setup, Tools, Settings at bottom | Preserved; extra actions moved into working Tools menu |
| Conversation | Right user bubble; left orange assistant heading; fenced shell code | Matched; actual copy button writes selected code to clipboard |
| Provider/model | Offline Intel selector, Choose model | Matched; real provider/model commands remain connected |
| Composer | Attachment, Message Ooonana, orange send, Enter/Shift+Enter hint | Matched; text insertion is editable before any send |
| Palette | Graphite/orange, solid surfaces | Concept's subtle gradients intentionally flattened for user's opaque theme |
| Typography/density | Compact and wide layouts | Inspected at 1080x730, 740x560, and concept-native 1584x992 display sizes; wide sidebar/content scale fixed |
| Controls | Native red/yellow/green traffic controls | Visible symbols intentionally kept for accessibility; GTK native icon family substitutes generated icon strokes |

Copy diff: reference chat/navigation/provider/composer labels preserved. Delete-chat control added because private persistent history needs explicit removal; empty state explains provider/model setup. Sample conversation is test-only and labeled as such in README. No fabricated provider response appears in production.

Core functional boundaries: private history round-trip and file permissions, corrupted-history preservation, bounded context transport, rejection of injected system-role context, real CLI process cancellation, thread selection/search/new/delete, Enter versus Shift+Enter, attachments, and code copying. Provider inference is intentionally not claimed from UI fixtures. Request cancellation kills only the owned CLI process, never the shared API.
