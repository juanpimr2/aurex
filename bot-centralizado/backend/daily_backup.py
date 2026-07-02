# -*- coding: utf-8 -*-
"""
Aurex — Salvaguarda diaria de datos (B3 + B4)
=============================================
Punto de entrada unico para el cron diario de backup. Hace, en orden:
  1) Dump de la BD SQLite a CSV versionable (B4) -> aurex_trades_dump.csv
  2) Backup local con verificacion de integridad + poda (B3)
  3) Resumen y pista de git para versionar el dump

SOLO LECTURA sobre datos de trading. No toca broker, ordenes ni estrategia.
Registra el resultado en el log mensual (B2).

Uso:
  python daily_backup.py
"""
import os
import sys

from aurex_logger import get_logger
import dump_db
import backup_aurex

log = get_logger('daily_backup')


def main():
    log.info('START daily_backup')

    # F1.1: acumular velas historicas ANTES del backup (asi la copia del dia
    # las incluye). Solo lectura sobre el broker; si falla, NO bloquea el backup.
    try:
        import collect_candles
        res = collect_candles.collect()
        resumen = ', '.join(tf + ':+' + str(v) for tf, v in res.items() if v >= 0)
        log.info('Candles: ' + resumen)
        print('[DAILY] Velas acumuladas -> ' + resumen)
    except Exception as e:
        log.error('Candle collector fallo: ' + str(e))
        print('AVISO: collector de velas fallo (' + str(e) + '), sigo con backup')

    try:
        n = dump_db.dump()
        log.info('DB dump: ' + str(n) + ' filas')
    except Exception as e:
        log.error('DB dump fallo: ' + str(e))
        print('ERROR en dump_db: ' + str(e))
        n = -1

    try:
        dest = backup_aurex.create_backup()
        ok = backup_aurex.verify_backup(dest)
        log.info('Backup ' + ('OK' if ok else 'FALLO') + ' -> ' + dest)
    except Exception as e:
        log.error('Backup fallo: ' + str(e))
        print('ERROR en backup: ' + str(e))
        sys.exit(1)

    print()
    print('[DAILY] Salvaguarda completada.')
    print('[DAILY] Para versionar el dump de la BD en git:')
    print('        git add bot-centralizado/backend/aurex_trades_dump.csv && '
          'git commit -m "data: dump diario BD" && git push')
    log.info('END daily_backup')


if __name__ == '__main__':
    main()
