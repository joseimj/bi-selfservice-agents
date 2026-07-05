# Frontend A2UI (superficie de UI generativa)

El orquestador expuesto en Cloud Run (`orchestrator_a2a_url` en los outputs de
Terraform) es un servidor **A2A** cuyo AgentCard anuncia la extensión **A2UI**
(`https://a2ui.org/a2a-extension/a2ui/v0.9`). Los payloads A2UI viajan como
`DataPart` con MIME `application/json+a2ui`.

Para renderizarlos necesitas un host con un renderer A2UI. Opciones mantenidas:

1. **Lit (web)** — renderer de referencia en el repo de A2UI (`renderers/lit`).
   Conecta el cliente A2A al endpoint del orquestador y pasa cada DataPart
   `application/json+a2ui` al `<a2ui-surface>`.
2. **Angular** — renderer oficial equivalente.
3. **Flutter (GenUI SDK)** — móvil/desktop/web.
4. **CopilotKit + AG-UI** — el template "A2UI Starter" de CopilotKit te da el
   scaffolding completo (Next.js) apuntando a un agente ADK; solo cambias la
   URL del agente por la del orquestador.

Flujo esperado en la UI:

1. El usuario pide "quiero un tablero de ventas por país".
2. El orquestador consulta al Catalog Agent (A2A) y devuelve un **wizard A2UI**
   (Card con selección de explore, campos, tipos de gráfico, layout).
3. El usuario completa el wizard; el submit vuelve como mensaje al agente.
4. El Builder crea el dashboard nativo en Looker; el orquestador devuelve un
   **Card de preview** con render, link SSO firmado y botón "Ajustar".

Nota: la superficie de **Gemini Enterprise** consume el mismo orquestador vía
Agent Engine, pero como GE no renderiza A2UI, ahí la experiencia degrada a
texto + imágenes inline (artifacts ADK) + links firmados. Misma lógica, dos
superficies.
