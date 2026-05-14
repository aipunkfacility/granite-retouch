"""Реестр пресетов — UI-метаданные (бренд, категория, alert).

Разделён из config.py по принципу ответственности:
  - config.py — данные ядра пайплайна (DEFAULTS, миграции, валидация)
  - presets_catalog.py — UI-метаданные для фронтенда (бренд, label, категория, alert)

Фронтенд получает каталог через API: GET /api/presets/catalog
"""

PRESET_CATALOG = {
    # --- Базовые (технология) ---
    "laser-default": {
        "label": "Laser CO2 20-40W",
        "category": "technology",
        "machine_type": "laser_standard",
    },
    "laser-80w-default": {
        "label": "Laser 80W+",
        "category": "technology",
        "machine_type": "laser_80w",
    },
    "impact-default": {
        "label": "Ударный",
        "category": "technology",
        "machine_type": "impact",
    },
    # --- Производитель / модель ---
    "mirtels-impact": {
        "label": "Mirtels (ударный, все модели)",
        "category": "machine",
        "machine_type": "impact",
        "brand": "mirtels",
        "combo_group": "mirtels",
    },
    "mirtels-laser-co2": {
        "label": "Mirtels CO2 лазер",
        "category": "machine",
        "machine_type": "laser_standard",
        "brand": "mirtels",
        "combo_group": "mirtels",
    },
    "sauno-graph-3kl-laser": {
        "label": "САУНО График-3КЛ (CO2 40W)",
        "category": "machine",
        "machine_type": "laser_standard",
        "brand": "sauno",
        "combo_group": "sauno",
    },
    "sauno-graph-3kld-laser80w": {
        "label": "САУНО График-3КЛД (диод 80W)",
        "category": "machine",
        "machine_type": "laser_80w",
        "brand": "sauno",
        "combo_group": "sauno",
    },
    "sauno-graph-3k-impact": {
        "label": "САУНО График-3К (ударный)",
        "category": "machine",
        "machine_type": "impact",
        "brand": "sauno",
        "combo_group": "sauno",
    },
    "stanzone-laser-1bit": {
        "label": "Stanzone (лазер, 1-bit)",
        "category": "machine",
        "machine_type": "laser_80w",
        "brand": "stanzone",
        "combo_group": "stanzone",
        "alert": "Лазерный модуль Stanzone работает ТОЛЬКО в 1-bit!",
    },
    "stanzone-impact": {
        "label": "Stanzone (ударный)",
        "category": "machine",
        "machine_type": "impact",
        "brand": "stanzone",
        "combo_group": "stanzone",
    },
    "stonegraf-impact": {
        "label": "STONE-ГРАФ (ударный)",
        "category": "machine",
        "machine_type": "impact",
        "brand": "stonegraf",
        "alert": "DPI в BMP критичен — станок не распознаёт файл при некорректном DPI",
    },
}
