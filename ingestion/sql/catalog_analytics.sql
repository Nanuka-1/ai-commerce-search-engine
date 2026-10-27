-- =====================================================================
-- Аналитика изменений каталога TopSport (таблицы scrape_runs, product_changes)
--
-- Все запросы смотрят ПОСЛЕДНИЙ прогон: CTE run = MAX(id) из scrape_runs.
-- Чтобы смотреть период (например, неделю), замените в запросе CTE run на:
--   run AS (SELECT id FROM scrape_runs WHERE started_at >= now() - interval '7 days')
-- и "pc.run_id = run.id" продолжит работать (JOIN по списку прогонов).
--
-- "Страница" (модель в карточке сайта) = product_url без ?size=...
-- Правило: отчёты фильтруют конкретный change_type / field, а не все updated —
-- изменения наших правил обогащения (model_family, category_slug, ...) это шум.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 0. История прогонов: размер каталога и изменения по дням
-- ---------------------------------------------------------------------
SELECT id,
       started_at::date                              AS day,
       finished_at - started_at                      AS duration,
       urls_total, urls_failed,
       created_count, updated_count, deactivated_count, reactivated_count
FROM scrape_runs
ORDER BY id DESC;


-- ---------------------------------------------------------------------
-- 1. НОВИНКИ: новая модель (вся страница новая) или новый размер у старой модели
-- ---------------------------------------------------------------------
WITH run AS (SELECT MAX(id) AS id FROM scrape_runs),
created AS (
    SELECT pc.sku
    FROM product_changes pc
    JOIN run ON pc.run_id = run.id
    WHERE pc.change_type = 'created'
),
pages AS (
    SELECT split_part(p.product_url, '?', 1)                       AS page,
           MAX(p.brand)                                            AS brand,
           MAX(p.name)                                             AS name,
           MIN(p.price)                                            AS price_from,
           COUNT(*) FILTER (WHERE p.sku IN (SELECT sku FROM created)) AS new_variants,
           COUNT(*)                                                AS all_variants,
           STRING_AGG(p.size, ', ' ORDER BY p.size)
               FILTER (WHERE p.sku IN (SELECT sku FROM created))   AS new_sizes
    FROM products p
    GROUP BY 1
    HAVING COUNT(*) FILTER (WHERE p.sku IN (SELECT sku FROM created)) > 0
)
SELECT CASE WHEN new_variants = all_variants THEN 'новая модель'
            ELSE 'новый размер' END                                AS kind,
       brand, name, new_sizes, price_from, page
FROM pages
ORDER BY kind, brand, name;

-- 1a. Сводка новинок (проверка: SUM(variants) = created_count прогона)
WITH run AS (SELECT MAX(id) AS id FROM scrape_runs),
created AS (
    SELECT pc.sku FROM product_changes pc JOIN run ON pc.run_id = run.id
    WHERE pc.change_type = 'created'
),
pages AS (
    SELECT split_part(p.product_url, '?', 1) AS page,
           COUNT(*) FILTER (WHERE p.sku IN (SELECT sku FROM created)) AS new_variants,
           COUNT(*) AS all_variants
    FROM products p
    GROUP BY 1
    HAVING COUNT(*) FILTER (WHERE p.sku IN (SELECT sku FROM created)) > 0
)
SELECT CASE WHEN new_variants = all_variants THEN 'новая модель'
            ELSE 'новый размер' END AS kind,
       COUNT(*)          AS pages,
       SUM(new_variants) AS variants
FROM pages
GROUP BY 1;


-- ---------------------------------------------------------------------
-- 2. ЦЕНА ↓ / ↑ (одна строка на страницу и пару цен; варианты одной модели
--    обычно меняют цену вместе)
-- ---------------------------------------------------------------------
WITH run AS (SELECT MAX(id) AS id FROM scrape_runs)
SELECT CASE WHEN pc.new_price < pc.old_price THEN 'подешевел'
            ELSE 'подорожал' END                                   AS direction,
       p.brand,
       MAX(p.name)                                                 AS name,
       pc.old_price,
       pc.new_price,
       ROUND(((pc.new_price - pc.old_price)
              / NULLIF(pc.old_price, 0) * 100)::numeric, 1)        AS change_pct,
       COUNT(*)                                                    AS variants,
       split_part(p.product_url, '?', 1)                           AS page
FROM product_changes pc
JOIN run ON pc.run_id = run.id
JOIN products p ON p.sku = pc.sku
WHERE pc.field = 'price'
  AND pc.old_price IS NOT NULL
  AND pc.new_price IS NOT NULL
GROUP BY 1, p.brand, pc.old_price, pc.new_price, split_part(p.product_url, '?', 1)
ORDER BY change_pct;

-- 2a. Сводка цен (проверка: SUM(variants) = число строк field='price' в прогоне)
WITH run AS (SELECT MAX(id) AS id FROM scrape_runs)
SELECT CASE WHEN pc.new_price < pc.old_price THEN 'подешевел'
            ELSE 'подорожал' END                                   AS direction,
       COUNT(DISTINCT split_part(p.product_url, '?', 1))           AS pages,
       COUNT(*)                                                    AS variants,
       ROUND(AVG((pc.new_price - pc.old_price)
                 / NULLIF(pc.old_price, 0) * 100)::numeric, 1)     AS avg_change_pct
FROM product_changes pc
JOIN run ON pc.run_id = run.id
JOIN products p ON p.sku = pc.sku
WHERE pc.field = 'price'
GROUP BY 1;


-- ---------------------------------------------------------------------
-- 3. ПРОПАВШИЕ: товар снят целиком (не осталось активных размеров)
--    или распроданы отдельные размеры
-- ---------------------------------------------------------------------
WITH run AS (SELECT MAX(id) AS id FROM scrape_runs),
gone AS (
    SELECT pc.sku
    FROM product_changes pc
    JOIN run ON pc.run_id = run.id
    WHERE pc.change_type = 'deactivated'
),
pages AS (
    SELECT split_part(p.product_url, '?', 1)                       AS page,
           MAX(p.brand)                                            AS brand,
           MAX(p.name)                                             AS name,
           COUNT(*) FILTER (WHERE p.sku IN (SELECT sku FROM gone)) AS gone_variants,
           COUNT(*) FILTER (WHERE p.is_active)                     AS active_left,
           STRING_AGG(p.size, ', ' ORDER BY p.size)
               FILTER (WHERE p.sku IN (SELECT sku FROM gone))      AS gone_sizes
    FROM products p
    GROUP BY 1
    HAVING COUNT(*) FILTER (WHERE p.sku IN (SELECT sku FROM gone)) > 0
)
SELECT CASE WHEN active_left = 0 THEN 'снят целиком'
            ELSE 'распроданы размеры' END                          AS kind,
       brand, name, gone_sizes, active_left, page
FROM pages
ORDER BY kind, brand, name;

-- 3a. Сводка пропавших (проверка: SUM(variants) = deactivated_count прогона)
WITH run AS (SELECT MAX(id) AS id FROM scrape_runs),
gone AS (
    SELECT pc.sku FROM product_changes pc JOIN run ON pc.run_id = run.id
    WHERE pc.change_type = 'deactivated'
),
pages AS (
    SELECT split_part(p.product_url, '?', 1) AS page,
           COUNT(*) FILTER (WHERE p.sku IN (SELECT sku FROM gone)) AS gone_variants,
           COUNT(*) FILTER (WHERE p.is_active) AS active_left
    FROM products p
    GROUP BY 1
    HAVING COUNT(*) FILTER (WHERE p.sku IN (SELECT sku FROM gone)) > 0
)
SELECT CASE WHEN active_left = 0 THEN 'снят целиком'
            ELSE 'распроданы размеры' END AS kind,
       COUNT(*)           AS pages,
       SUM(gone_variants) AS variants
FROM pages
GROUP BY 1;


-- ---------------------------------------------------------------------
-- 4. ДИНАМИКА ПО БРЕНДАМ за прогон: +новые / −пропавшие / изменения цен
-- ---------------------------------------------------------------------
WITH run AS (SELECT MAX(id) AS id FROM scrape_runs),
by_brand AS (
    SELECT p.brand,
           COUNT(*) FILTER (WHERE pc.change_type = 'created')     AS added,
           COUNT(*) FILTER (WHERE pc.change_type = 'deactivated') AS removed,
           COUNT(*) FILTER (WHERE pc.field = 'price')             AS price_changes
    FROM product_changes pc
    JOIN run ON pc.run_id = run.id
    JOIN products p ON p.sku = pc.sku
    WHERE pc.change_type IN ('created', 'deactivated') OR pc.field = 'price'
    GROUP BY p.brand
)
SELECT brand, added, removed, price_changes
FROM by_brand
ORDER BY added + removed DESC;