<div align="center">

[English](../../README.md) · [简体中文](README_zh.md) · [日本語](README_ja.md) · [한국어](README_ko.md) · **Español** · [Italiano](README_it.md)

# IRP: Construye cualquier artículo. Demuestra cada afirmación.

### Un servidor MCP y una CLI para que tu agente de programación convierta un artículo de investigación en código funcional, lo ejecute y demuestre, afirmación por afirmación, cuánto se acerca.

**Dale un artículo. Recibe código funcional y un informe que puedes comprobar sin confiar en el agente.**

[![PyPI version](https://img.shields.io/pypi/v/irp?style=flat-square&color=3775a9)](https://pypi.org/project/irp-agents/)
[![MCP tool catalog](https://img.shields.io/badge/MCP-tool_catalog-5c4ee5?style=flat-square)](../mcp-contracts.md#generated-catalog)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776ab?style=flat-square&logo=python&logoColor=white)](#qué-puedes-reproducir)
[![MIT license](https://img.shields.io/badge/license-MIT-f4c430?style=flat-square)](../../LICENSE)

[Inicio rápido](#inicio-rápido) · [Cómo funciona](#cómo-funciona) · [El informe](#el-informe) · [Qué puedes reproducir](#qué-puedes-reproducir) · [Preguntas frecuentes](#preguntas-frecuentes) · [Documentación](#documentación)

<code>uvx irp-agents setup</code>

</div>

> [!IMPORTANT]
> Obtén IRP solo desde [Noshadi-sec/irp](https://github.com/Noshadi-sec/irp) o el
> [paquete irp en PyPI](https://pypi.org/project/irp-agents/). Un nombre de
> repositorio parecido o un README copiado no demuestran que una descarga sea oficial.

<div align="center">

<img src="../assets/irp-flow.svg" alt="Flujo de IRP: le pides a tu agente que construya un artículo; el agente lee el artículo, registra las afirmaciones, escribe el código y decide las ejecuciones con las herramientas de IRP; IRP obtiene el artículo, ejecuta el código y registra cada paso en un registro de evidencias encadenado por hashes; el informe se escribe solo a partir de ese registro." width="900" />

</div>

---

¿Encontraste un artículo sin código, o con código en el que no confías? Pídele a tu
agente que lo construya con IRP. El agente lee el artículo, registra cada número
que afirma, escribe la implementación, la ejecuta y compara los resultados. IRP se
encarga de obtener, ejecutar y registrar, y rechaza los atajos: un número tecleado a mano
nunca cuenta, una ejecución acortada nunca cuenta y el informe se escribe solo a partir
del registro de evidencias.

IRP conecta tu agente (Claude Code, Codex o Cursor) con herramientas para leer el
artículo, crear entornos, ejecutar, medir y emitir veredictos. Puedes usar las mismas
herramientas desde tu terminal. Todo se ejecuta localmente; IRP nunca llama a un modelo.

## Inicio rápido

### Configura tu agente

Con [uv](https://docs.astral.sh/uv/) instalado, ejecuta:

```bash
uvx irp-agents setup
```

Elige tus agentes, revisa los cambios propuestos y apruébalos. Setup añade el servidor
MCP de IRP y su skill de flujo de trabajo, con copias de seguridad de la configuración
existente. Después, reinicia tu agente.

Setup es compatible con Claude Code, Codex y Cursor. Otros clientes MCP pueden usar el
[registro manual](../installation.md#manual-registration).

### Pídeselo a tu agente

```text
Build arXiv 2501.12345 and check Table 2.
```

Recibes una carpeta de código funcional y un informe: cada afirmación, el número del
artículo, tu número y un veredicto.

### Usa la terminal

Cada herramienta es también un comando. Obtén un artículo en un estudio nuevo y lee su índice:

```bash
irp fetch 2501.12345 --study ~/studies/example
irp section index --study ~/studies/example
```

Para instalar el comando `irp`:

```bash
uv tool install irp-agents
irp --help
```

Consulta la [guía de la CLI](../cli.md) para el flujo completo desde la terminal.

### Comprueba que todo está listo

```bash
irp doctor
```

Doctor revisa Python, uv, git, Docker, las GPU, el espacio en disco y el registro de tus
agentes, sin cambiar nada.

### Actualizan IRP

```bash
irp update
```

Con uvx, actualiza la configuración de tu agente con `uvx irp-agents@latest setup`, revisa
el plan y reinicia el agente.

## Cómo funciona

Tu agente piensa; IRP actúa y guarda los comprobantes. El agente lee el artículo,
escribe el código y decide qué ejecutar. Cada acción pasa por un único núcleo, así que la
CLI y el servidor MCP se comportan igual, y cada paso queda en un registro de evidencias de
solo anexado, encadenado por hashes. El informe se construye solo a partir de ese registro.

| Etapa | Herramienta | Qué hace |
| --- | --- | --- |
| Lectura | `fetch_paper` | Descarga el código LaTeX de arXiv o el PDF, calcula su hash y lo divide en secciones |
| Lectura | `get_section`, `get_page_image` | Devuelve el texto de una sección con archivo y número de línea, o una página como imagen para ecuaciones y figuras |
| Afirmaciones | `add_claim`, `list_claims` | Registra cada afirmación: métrica, valor, dónde aparece y el umbral de éxito |
| Plan | `add_guess` | Registra un detalle que falta, la elección hecha y por qué |
| Plan | `map_method` | Enlaza una ecuación o un paso de algoritmo con un archivo y una línea |
| Construcción | `create_env` | Crea un entorno uv o una imagen Docker y escribe el archivo de bloqueo |
| Ejecución | `run`, `run_status` | Ejecuta un comando; guarda salida, código de salida, tiempo, memoria, semilla, commit y archivos |
| Ejecución | `run_remote` | Lo mismo en una GPU de pago, tras una estimación de coste y una aprobación |
| Medición | `extract_metrics` | Extrae números de registros y archivos de resultados, con archivo y línea |
| Veredicto | `compare`, `add_note` | Pone afirmación y medición lado a lado y da uno de cuatro veredictos |
| Informe | `report`, `verify`, `study_status` | Escribe report.md y report.json a partir del registro; vuelve a comprobar la cadena de hashes |

La skill de flujo de trabajo da al agente seis reglas estrictas, y las herramientas las
hacen cumplir siempre que pueden:

1. Nunca teclees, estimes ni copies un número como resultado.
2. Nunca cambies el método del artículo para que una ejecución funcione; registra una suposición.
3. Informa "no se pudo ejecutar" con el error que lo bloquea en lugar de forzarlo.
4. Ejecuta primero la versión fiel más pequeña; las ejecuciones acortadas nunca cuentan.
5. Registra cada afirmación antes de escribir código.
6. Pregunta antes de cualquier cómputo de pago.

## El informe

El informe es el producto: una persona debe poder comprobar cada veredicto sin confiar en el
agente. Tiene cinco partes: la tabla de afirmaciones, cuatro veredictos (reproducido, cercano,
no reproducido en esta ejecución, no se pudo ejecutar), la lista de suposiciones, el mapa del
método de ecuaciones a líneas de código y la procedencia (ID y versión de arXiv, hashes de
archivos, commit de git, archivos de bloqueo, GPU, semillas, cada comando con su código de
salida y un comando verify que vuelve a comprobar la cadena de hashes).

El agente no puede terminar hasta que cada afirmación tenga un veredicto con evidencia.

Ejemplo de `report.md` (números inventados):

```markdown
# Reproduction report: Example Paper (arXiv 2501.12345v2)

Result: 2 reproduced, 1 close, 1 could not run (of 4 claims)

| Claim | Where | Paper | Ours | Verdict |
| --- | --- | --- | --- | --- |
| c1 Test accuracy | Table 2, row 3 | 94.1% | 93.8% (3 seeds, std 0.2) | close |
| c2 Training loss | Figure 4 | 0.31 | 0.31 (3 seeds) | reproduced |
| c3 Speed-up | Section 5.2 | 2.0x | 2.1x | reproduced |
| c4 ImageNet top-1 | Table 3 | 81.2% | not run: needs 8 GPUs for 2 days | could not run |
```

Consulta [evidencias e informe](../evidence-and-report.md) para cada campo.

## Qué puedes reproducir

IRP requiere Python 3.11+ en macOS o Linux. Las demás herramientas dependen del artículo:

| Necesidad | Qué usan IRP | Requisitos y guía |
| --- | --- | --- |
| Lectura del artículo | Primero el código LaTeX de arXiv, después el PDF, e imágenes de página para ecuaciones y figuras | Acceso a arXiv; [lectura de artículos](../paper-intake.md) |
| Mejor estructura del PDF | Docling para texto y tablas | Opcional `irp-agents[docling]` |
| Entornos | Entornos virtuales uv con archivo de bloqueo, o imágenes Docker para aislar | uv o Docker; [entornos](../environments.md) |
| Cómputo | Tu CPU o GPU; sandboxes GPU de Modal tras estimación y aprobación (experimental) | Opcional `irp-agents[modal]`; [cómputo](../compute.md) |
| Agentes | Claude Code, Codex, Cursor; cualquier cliente MCP a mano | [instalación](../installation.md) |

IRP admite artículos computacionales: aprendizaje automático, algoritmos y simulaciones.
No admite trabajo de laboratorio húmedo ni nada relacionado con armas.

## Casos destacados

Aún no hay casos destacados publicados. Cada uno tendrá su propio repositorio e informe.
Sigue el progreso en la [hoja de ruta](../roadmap.md).

## Preguntas frecuentes

<details>
<summary><strong>¿Qué agentes pueden usar IRP?</strong></summary>

Cualquier agente que admita servidores MCP locales. Setup configura Claude Code, Codex y Cursor.

</details>

<details>
<summary><strong>¿IRP llama a un modelo de IA o sube mi artículo?</strong></summary>

No. Tu agente es el cerebro; IRP nunca llama a un modelo y no tiene clave de API.
Descarga artículos de arXiv, instala paquetes con uv o Docker y ejecuta código en tu máquina.

</details>

<details>
<summary><strong>¿Es seguro ejecutar el código de un artículo?</strong></summary>

Un entorno virtual uv no es un sandbox: el código se ejecuta con tus permisos. Usa
`backend: "docker"` para código que no escribiste o en el que no confías. Consulta la
[política de seguridad](../../SECURITY.md).

</details>

<details>
<summary><strong>¿Qué significa "no reproducido"?</strong></summary>

Que esta ejecución, con las suposiciones registradas, no alcanzó el número del artículo dentro
del umbral indicado. El informe dice "not reproduced by this run" y enumera cada suposición. Es
evidencia sobre un intento, no un veredicto sobre el artículo; contacta con los autores antes de
publicarlo.

</details>

<details>
<summary><strong>¿Puede IRP gastar dinero?</strong></summary>

Solo en GPU de pago, solo después de que registres un precio y un presupuesto en una terminal
con `irp budget`, y solo después de que apruebes la estimación que te muestra el agente. El
límite de tiempo de la ejecución es igual a las horas estimadas.

</details>

## Documentación

- [Instalación y configuración](../installation.md)
- [CLI](../cli.md)
- [Contratos MCP](../mcp-contracts.md) y [prompts](../mcp-prompts.md)
- [Evidencias e informe](../evidence-and-report.md)
- [Lectura de artículos](../paper-intake.md), [entornos](../environments.md) y [cómputo](../compute.md)
- [Benchmarks](../benchmarks.md) y [hoja de ruta](../roadmap.md)

Informa de vulnerabilidades a través de [SECURITY.md](../../SECURITY.md).

## Aviso legal

Consulta [DISCLAIMER.md](../../DISCLAIMER.md) para el uso responsable. Un veredicto "no
reproducido" es evidencia sobre una ejecución, no un juicio sobre el artículo ni sus autores.

## Contribuir

Las contribuciones son bienvenidas. Consulta [CONTRIBUTING.md](../../CONTRIBUTING.md).

## Licencia

[MIT](../../LICENSE). El material de terceros conserva sus propias licencias; consulta los
[avisos de terceros](../../THIRD_PARTY_NOTICES.md).
