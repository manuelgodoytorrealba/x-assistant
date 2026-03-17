# README — comandos diarios de `x-assistant`

Este README resume los comandos más importantes del proyecto para el uso diario, cómo añadir cuentas nuevas y cómo dejar activas unas cuentas sí y otras no.

---

## Respuesta rápida a tu duda principal

**Sí.**  
Si ya agregaste esas cuentas a `accounts_to_watch` y tienen:

- `is_active = 1`
- `usage_mode = 'both'` o compatible con el modo que ejecutes

entonces al correr:

```bash
PYTHONPATH=. python scripts/fetch_tweets.py --mode inspiration
```

el bot **sí correrá con esas cuentas nuevas**.

Tu `fetch_tweets.py` está leyendo desde `accounts_to_watch` y filtra por `usage_mode`, así que esas cuentas nuevas entran en el flujo si están activas.

---

# 1) Comandos que usarás casi todos los días

## Activar entorno virtual
```bash
source .venv/bin/activate
```

## Inicializar base de datos
```bash
PYTHONPATH=. python scripts/init_db.py
```

## Limpiar runtime
```bash
PYTHONPATH=. python scripts/reset_runtime_data.py
```

## Ejecutar fetch en modo inspiración
```bash
PYTHONPATH=. python scripts/fetch_tweets.py --mode inspiration
```

## Ejecutar fetch en modo reply
```bash
PYTHONPATH=. python scripts/fetch_tweets.py --mode reply
```

## Ejecutar pipeline completo
```bash
PYTHONPATH=. python scripts/run_real_pipeline.py
```

## Levantar API local
```bash
uvicorn app.main:app --reload
```

---

# 2) Flujo diario recomendado

## Flujo corto
```bash
source .venv/bin/activate
PYTHONPATH=. python scripts/reset_runtime_data.py
PYTHONPATH=. python scripts/fetch_tweets.py --mode inspiration
```

## Flujo completo
```bash
source .venv/bin/activate
PYTHONPATH=. python scripts/init_db.py
PYTHONPATH=. python scripts/reset_runtime_data.py
PYTHONPATH=. python scripts/fetch_tweets.py --mode inspiration
PYTHONPATH=. python scripts/run_real_pipeline.py
```

---

# 3) Ver cuentas guardadas en la base de datos

## Ver todas las cuentas
```bash
sqlite3 db/app.db "SELECT id, handle, topic_hint, author_priority, is_active, usage_mode FROM accounts_to_watch ORDER BY topic_hint ASC, author_priority DESC, handle ASC;"
```

## Ver solo las cuentas activas de Jano
```bash
sqlite3 db/app.db "SELECT id, handle, topic_hint, author_priority, is_active, usage_mode FROM accounts_to_watch WHERE is_active = 1 AND topic_hint = 'jano' ORDER BY author_priority DESC, handle ASC;"
```

## Ver solo las cuentas activas de Ensō
```bash
sqlite3 db/app.db "SELECT id, handle, topic_hint, author_priority, is_active, usage_mode FROM accounts_to_watch WHERE is_active = 1 AND topic_hint = 'enso' ORDER BY author_priority DESC, handle ASC;"
```

## Buscar duplicados
```bash
sqlite3 db/app.db "SELECT handle, COUNT(*) as total FROM accounts_to_watch GROUP BY handle HAVING COUNT(*) > 1;"
```

---

# 4) Añadir cuentas nuevas

## Insertar nuevas cuentas sin duplicarlas
```bash
sqlite3 db/app.db "
INSERT INTO accounts_to_watch (handle, topic_hint, author_priority, is_active, usage_mode)
SELECT 'Melpomnes', 'jano', 5, 1, 'both'
WHERE NOT EXISTS (SELECT 1 FROM accounts_to_watch WHERE handle = 'Melpomnes');

INSERT INTO accounts_to_watch (handle, topic_hint, author_priority, is_active, usage_mode)
SELECT 'archaeologyart', 'jano', 5, 1, 'both'
WHERE NOT EXISTS (SELECT 1 FROM accounts_to_watch WHERE handle = 'archaeologyart');

INSERT INTO accounts_to_watch (handle, topic_hint, author_priority, is_active, usage_mode)
SELECT 'artenpedia', 'jano', 5, 1, 'both'
WHERE NOT EXISTS (SELECT 1 FROM accounts_to_watch WHERE handle = 'artenpedia');

INSERT INTO accounts_to_watch (handle, topic_hint, author_priority, is_active, usage_mode)
SELECT 'HistoriaJack', 'jano', 5, 1, 'both'
WHERE NOT EXISTS (SELECT 1 FROM accounts_to_watch WHERE handle = 'HistoriaJack');

INSERT INTO accounts_to_watch (handle, topic_hint, author_priority, is_active, usage_mode)
SELECT 'X_ArtGallery', 'jano', 5, 1, 'both'
WHERE NOT EXISTS (SELECT 1 FROM accounts_to_watch WHERE handle = 'X_ArtGallery');

INSERT INTO accounts_to_watch (handle, topic_hint, author_priority, is_active, usage_mode)
SELECT 'MuseoThyssen', 'jano', 5, 1, 'both'
WHERE NOT EXISTS (SELECT 1 FROM accounts_to_watch WHERE handle = 'MuseoThyssen');

INSERT INTO accounts_to_watch (handle, topic_hint, author_priority, is_active, usage_mode)
SELECT 'ArteInformado', 'jano', 5, 1, 'both'
WHERE NOT EXISTS (SELECT 1 FROM accounts_to_watch WHERE handle = 'ArteInformado');

INSERT INTO accounts_to_watch (handle, topic_hint, author_priority, is_active, usage_mode)
SELECT '_ArtMuseum', 'jano', 5, 1, 'both'
WHERE NOT EXISTS (SELECT 1 FROM accounts_to_watch WHERE handle = '_ArtMuseum');

INSERT INTO accounts_to_watch (handle, topic_hint, author_priority, is_active, usage_mode)
SELECT 'DailyClassicArt', 'jano', 5, 1, 'both'
WHERE NOT EXISTS (SELECT 1 FROM accounts_to_watch WHERE handle = 'DailyClassicArt');

INSERT INTO accounts_to_watch (handle, topic_hint, author_priority, is_active, usage_mode)
SELECT 'rinconartex', 'jano', 5, 1, 'both'
WHERE NOT EXISTS (SELECT 1 FROM accounts_to_watch WHERE handle = 'rinconartex');
"
```

## Actualizar esas cuentas si ya existen
```bash
sqlite3 db/app.db "
UPDATE accounts_to_watch
SET topic_hint = 'jano',
    author_priority = 5,
    is_active = 1,
    usage_mode = 'both'
WHERE handle IN (
  'Melpomnes',
  'archaeologyart',
  'artenpedia',
  'HistoriaJack',
  'X_ArtGallery',
  'MuseoThyssen',
  'ArteInformado',
  '_ArtMuseum',
  'DailyClassicArt',
  'rinconartex'
);
"
```

---

# 5) Activar o desactivar cuentas

## Desactivar una cuenta concreta
```bash
sqlite3 db/app.db "UPDATE accounts_to_watch SET is_active = 0 WHERE handle = 'Melpomnes';"
```

## Activar una cuenta concreta
```bash
sqlite3 db/app.db "UPDATE accounts_to_watch SET is_active = 1 WHERE handle = 'Melpomnes';"
```

## Dejar activas solo las cuentas de Jano
```bash
sqlite3 db/app.db "UPDATE accounts_to_watch SET is_active = CASE WHEN topic_hint = 'jano' THEN 1 ELSE 0 END;"
```

## Dejar activas solo las cuentas de Ensō
```bash
sqlite3 db/app.db "UPDATE accounts_to_watch SET is_active = CASE WHEN topic_hint = 'enso' THEN 1 ELSE 0 END;"
```

## Volver a activar todas las cuentas
```bash
sqlite3 db/app.db "UPDATE accounts_to_watch SET is_active = 1;"
```

## Dejar activas solo unas cuentas concretas
```bash
sqlite3 db/app.db "UPDATE accounts_to_watch SET is_active = CASE WHEN handle IN ('Melpomnes', 'MuseoThyssen', 'DailyClassicArt') THEN 1 ELSE 0 END;"
```

## Activar varias cuentas concretas sin tocar las demás
```bash
sqlite3 db/app.db "UPDATE accounts_to_watch SET is_active = 1 WHERE handle IN ('Melpomnes', 'MuseoThyssen', 'DailyClassicArt');"
```

## Desactivar varias cuentas concretas sin tocar las demás
```bash
sqlite3 db/app.db "UPDATE accounts_to_watch SET is_active = 0 WHERE handle IN ('Melpomnes', 'MuseoThyssen', 'DailyClassicArt');"
```

---

# 6) Uso práctico: correr solo Jano sin tocar código

Tu script ahora mismo filtra por `usage_mode`, no por `topic_hint` desde CLI.

Así que, si quieres correr solo Jano **sin tocar código**, haces esto:

```bash
sqlite3 db/app.db "UPDATE accounts_to_watch SET is_active = CASE WHEN topic_hint = 'jano' THEN 1 ELSE 0 END;"
PYTHONPATH=. python scripts/fetch_tweets.py --mode inspiration
```

Y cuando termines, puedes volver a activar todo:

```bash
sqlite3 db/app.db "UPDATE accounts_to_watch SET is_active = 1;"
```

---

# 7) Resumen ultra corto

## Ver cuentas
```bash
sqlite3 db/app.db "SELECT handle, topic_hint, is_active, usage_mode FROM accounts_to_watch ORDER BY topic_hint, handle;"
```

## Correr fetch
```bash
PYTHONPATH=. python scripts/fetch_tweets.py --mode inspiration
```

## Correr pipeline
```bash
PYTHONPATH=. python scripts/run_real_pipeline.py
```

## Solo Jano
```bash
sqlite3 db/app.db "UPDATE accounts_to_watch SET is_active = CASE WHEN topic_hint = 'jano' THEN 1 ELSE 0 END;"
PYTHONPATH=. python scripts/fetch_tweets.py --mode inspiration
```

## Reactivar todas
```bash
sqlite3 db/app.db "UPDATE accounts_to_watch SET is_active = 1;"
```

---

# 8) Nota importante

El comando de fetch **no actualiza** la tabla `accounts_to_watch`.

Este comando:

```bash
PYTHONPATH=. python scripts/fetch_tweets.py --mode inspiration
```

solo:
- lee cuentas activas
- filtra por `usage_mode`
- procesa tweets

Las cuentas las cambias tú con `INSERT` y `UPDATE` en SQLite.

---

# 9) Verificación final

Después de agregar cuentas nuevas, puedes confirmar que están listas con:

```bash
sqlite3 db/app.db "SELECT handle, topic_hint, is_active, usage_mode FROM accounts_to_watch WHERE handle IN ('Melpomnes', 'archaeologyart', 'artenpedia', 'HistoriaJack', 'X_ArtGallery', 'MuseoThyssen', 'ArteInformado', '_ArtMuseum', 'DailyClassicArt', 'rinconartex') ORDER BY handle;"
```

Si salen con `is_active = 1` y `usage_mode = both`, ya entran en el fetch de inspiración.