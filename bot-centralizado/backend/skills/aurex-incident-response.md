# Skill: Respuesta a incidentes de Aurex

> Qué hacer cuando algo va mal. Prioridad absoluta: proteger el capital, no la operativa.

## Diagnóstico rápido (en este orden)
1. `python health_check.py` → veredicto + lista de problemas (exit 0/1/2)
2. `tail -50 logs/aurex_YYYY-MM.log` → errores recientes de monitores
3. Posiciones en broker: ¿hay GOLD abierto? ¿tiene SL y TP? (get_positions)
4. `python reconcile.py` → ¿cuadra el broker con nuestros registros?

## Escenarios conocidos
| Síntoma | Causa probable | Acción |
|---------|----------------|--------|
| Login fallido repetido | API caída / credenciales | Retry ya automático; si persiste >30min avisar usuario. NO operar a ciegas |
| PC se reinició | Corte de luz (histórico: PSU sospechosa) | Posiciones SEGURAS (SL/TP en broker). Recrear crons, verificar con health_check |
| Posición sin SL/TP | Bug TP-wipe (fixed) o apertura fallida | CRÍTICO: si es GOLD de Aurex, reponer SL/TP vía modify_position e investigar. Si es no-GOLD → es manual del usuario, NO TOCAR |
| Trade en log sin posición en broker | Cerró (normal) | El auto-close lo marca; confirmar P&L real con reconcile.py |
| Posición en broker sin log | Confirm falló al abrir (H3) | Registrarla a mano en el log con su dealId; vigilarla normalmente |
| Monitor sin correr | Sesión Claude caída (R1/B1) | Recrear crons ("recrea los crons"). SL/TP protegen mientras tanto |
| "NFP EN CURSO" incorrecto | Bug fecha macro_context (1er viernes) | Ignorar la etiqueta; verificar fecha real en bls.gov |

## Reglas de conducta en incidente
- **Nunca** cerrar/modificar posiciones manuales del usuario (NVDA etc.).
- **Nunca** improvisar trades para "compensar" un fallo.
- Ante duda entre operar o no operar → **no operar**.
- Documentar todo incidente: qué pasó, causa, fix, prevención (añadir aquí si es nuevo).
- Cambios de emergencia en código de ejecución → mínimos, verificados al momento, commit inmediato.
