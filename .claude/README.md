# Sistema de memoria del proyecto

Este directorio contiene la **memoria persistente** del proyecto, pensada para no
perder contexto en sesiones largas y para recuperar contexto en sesiones futuras
(multisesión). Está inspirada en cómo funciona la memoria humana.

## Archivo principal: `memory.yaml`

Modela cuatro tipos de memoria:

| Tipo | Sección | Qué guarda | Volatilidad |
|------|---------|-----------|-------------|
| Trabajo (working) | `trabajo` | Foco inmediato, siguiente paso, bloqueos | Se sobrescribe cada sesión |
| Episódica | `episodica` | Qué pasó y cuándo (bitácora cronológica) | Crece; se poda lo antiguo/irrelevante |
| Semántica | `semantica` | Hechos y decisiones estables (con su porqué) | Estable |
| Procedimental | `procedimental` | Cómo hacer las cosas (comandos, recetas) | Estable |

Además, `indice_archivos` es un "mapa mental" del repositorio.

## Protocolo de uso

1. **Al iniciar sesión:** leer `memory.yaml` (empezar por `meta.contexto_critico` y `trabajo`).
2. **Durante la sesión:** actualizar `trabajo.foco_actual` y `trabajo.siguiente_paso`;
   añadir hitos relevantes a `episodica` con su `importancia` (1-5).
3. **Al cerrar sesión (consolidación):** mover lo importante de `trabajo`/`episodica`
   hacia `semantica`/`procedimental`; podar entradas con `importancia < 3` ya superadas;
   actualizar `meta.ultima_actualizacion`.

La consolidación imita el paso de memoria de corto a largo plazo durante el sueño:
se conserva lo significativo, se descarta el ruido.
