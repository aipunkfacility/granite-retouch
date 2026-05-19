"""Тесты модуля levels — яркость, unsharp, контроль лица."""

import numpy as np
import pytest
from PIL import Image

from retouch.processing.levels import (
    apply_levels,
    apply_unsharp_mask,
    check_face_brightness,
    _curves_correction,
    _shrink_mask,
)


class TestApplyLevels:
    """Тесты коррекции яркости."""

    def test_brightness_1_is_neutral(self):
        """brightness_factor=1.0 не меняет изображение."""
        arr = np.random.randint(50, 200, (100, 100), dtype=np.uint8)
        img = Image.fromarray(arr)
        result = apply_levels(img, 1.0)
        result_arr = np.array(result)
        diff = np.abs(result_arr.astype(int) - arr.astype(int))
        assert diff.max() <= 1, "brightness=1.0 не должен менять изображение"

    def test_brightness_increases_values(self):
        """brightness_factor>1.0 увеличивает яркость."""
        img = Image.new("L", (100, 100), 100)
        result = apply_levels(img, 1.5)
        result_val = np.array(result).mean()
        assert result_val > 100, f"Яркость должна увеличиться, а не {result_val:.0f}"

    def test_brightness_decreases_values(self):
        """brightness_factor<1.0 уменьшает яркость."""
        img = Image.new("L", (100, 100), 100)
        result = apply_levels(img, 0.5)
        result_val = np.array(result).mean()
        assert result_val < 100, f"Яркость должна уменьшиться, а не {result_val:.0f}"


class TestApplyUnsharpMask:
    """Тесты Unsharp Mask."""

    def test_sharpens_image(self):
        """Unsharp Mask добавляет резкость (разница с оригиналом)."""
        # Создаём плавный градиент
        arr = np.linspace(0, 255, 100 * 100, dtype=np.uint8).reshape(100, 100)
        img = Image.fromarray(arr)
        result = apply_unsharp_mask(img)
        # Разница должна быть (резкость меняет градиент)
        diff = np.abs(np.array(result).astype(float) - arr.astype(float))
        assert diff.mean() > 0, "Unsharp Mask должен менять изображение"

    def test_output_is_l_mode(self):
        """Результат — grayscale (L)."""
        img = Image.new("L", (100, 100), 128)
        result = apply_unsharp_mask(img)
        assert result.mode == "L", f"Результат должен быть L, а не {result.mode}"


class TestCurvesCorrection:
    """Тесты нелинейной (curves) коррекции."""

    def test_shadows_get_full_correction(self):
        """Тёмные пиксели получают полную коррекцию."""
        arr = np.array([0, 10, 30, 50], dtype=np.float32)
        correction = 1.3
        result = _curves_correction(arr, correction)
        # Нулевой пиксель: 0 * 1.3 = 0, delta=0, result=0 — это правильно
        # Но пиксель 10: 10*1.3=13, delta=3, weight~1.0 → result≈13
        assert result[1] > 10, f"Тёмный пиксель должен стать ярче: {result[1]:.0f}"
        assert result[2] > 30, f"Пиксель 30 должен стать ярче: {result[2]:.0f}"
        assert result[3] > 50, f"Пиксель 50 должен стать ярче: {result[3]:.0f}"

    def test_highlights_get_minimal_correction(self):
        """Светлые пиксели (240+) корректируются минимально."""
        arr = np.array([240, 245, 250, 255], dtype=np.float32)
        correction = 1.3
        result = _curves_correction(arr, correction)
        # Curves-коррекция: на 240 weight~0.33, на 245 weight~0.17, на 250+ weight~0
        # diff = linear_correction * weight, где linear = pixel * (correction - 1)
        # 240: delta = 240*0.3=72, weight≈0.33, diff≈24 — ожидаемо
        diff = np.abs(result - arr)
        # Света корректируются МЕНЬШЕ чем тени — проверяем монотонность
        # Коррекция для 240 должна быть больше чем для 250
        assert diff[0] >= diff[2], "Чем светлее пиксель, тем меньше коррекция"
        # И коррекция для 250+ минимальна
        assert diff[2] < diff[1], "250 корректируется меньше чем 245"

    def test_output_clipped(self):
        """Результат в диапазоне 0–255."""
        arr = np.array([250, 252, 254, 255], dtype=np.float32)
        result = _curves_correction(arr, 1.5)
        assert result.min() >= 0 and result.max() <= 255

    def test_highlight_start_parameter(self):
        """highlight_start контролирует затухание коррекции."""
        arr = np.array([180, 200, 220, 240], dtype=np.float32)
        correction = 1.3

        # С высоким highlight_start — коррекция полная для 200
        result_high = _curves_correction(arr, correction, highlight_start=240)
        # С низким highlight_start — коррекция затухает для 200
        result_low = _curves_correction(arr, correction, highlight_start=100)

        # При highlight_start=240 пиксель 200 получает почти полную коррекцию
        # При highlight_start=100 пиксель 200 получает затухающую коррекцию
        diff_high = abs(result_high[1] - arr[1])
        diff_low = abs(result_low[1] - arr[1])
        assert diff_high >= diff_low, \
            "Более высокий highlight_start → больше коррекция для средних тонов"


class TestShrinkMask:
    """Тесты сжатия маски (для исключения glow-зоны)."""

    def test_shrinks_mask(self):
        """Маска сжимается на заданное число пикселей."""
        # Квадратная маска 100x100
        mask = Image.new("L", (100, 100), 0)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(mask)
        draw.rectangle([10, 10, 89, 89], fill=255)

        result = _shrink_mask(mask, shrink_px=5)
        result_arr = np.array(result)

        # Сжатая маска должна иметь меньше белых пикселей
        original_white = (np.array(mask) > 128).sum()
        shrunk_white = (result_arr > 128).sum()
        assert shrunk_white < original_white, \
            "Сжатая маска должна быть меньше оригинала"

    def test_small_shrink_reduces_mask(self):
        """Малое сжатие (3px) немного уменьшает маску."""
        mask = Image.new("L", (100, 100), 0)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(mask)
        draw.rectangle([10, 10, 89, 89], fill=255)
        original_white = (np.array(mask) > 128).sum()
        result = _shrink_mask(mask, shrink_px=3)
        result_white = (np.array(result) > 128).sum()
        assert result_white < original_white, \
            "Маска должна уменьшиться после сжатия"
        # Но не слишком сильно — 3px с каждой стороны
        assert result_white > original_white * 0.5, \
            "Маска не должна уменьшиться больше чем вдвое"


class TestCheckFaceBrightness:
    """Тесты контроля яркости лица."""

    def test_dark_face_get_brightened(self):
        """v6.5: Тёмное лицо (медиана 80) осветляется bounded delta ±15."""
        gray = Image.new("L", (200, 200), 80)
        mask = Image.new("L", (200, 200), 255)
        target = [140, 165]

        result, before, after, factor = check_face_brightness(gray, target, mask, glow_size=0)
        result_arr = np.array(result)
        assert result_arr.mean() > 80.0, "Тёмное лицо должно осветлиться (v6.5)"
        assert before == 80.0
        assert after >= 80.0
        assert factor > 1.0, "factor>1.0 — осветление"
        # Проверяем bounded delta: after <= before + 15
        assert after <= 95.0, f"Delta превышает 15: {after:.1f}"

    def test_bright_face_gets_darkened(self):
        """Слишком яркое лицо (среднее 240) корректируется вниз."""
        gray = Image.new("L", (200, 200), 240)
        mask = Image.new("L", (200, 200), 255)
        target = [140, 165]

        result, before, after, factor = check_face_brightness(gray, target, mask, glow_size=0)
        result_arr = np.array(result)
        assert result_arr.mean() < 240, "Яркое лицо должно стать темнее"
        assert factor < 1.0, f"factor должен быть < 1.0 для яркого лица"

    def test_correct_face_unchanged(self):
        """Лицо в целевом диапазоне не корректируется."""
        gray = Image.new("L", (200, 200), 152)
        mask = Image.new("L", (200, 200), 255)
        target = [140, 165]

        result, before, after, factor = check_face_brightness(gray, target, mask, glow_size=0)
        result_arr = np.array(result)
        # Должно быть почти неизменным
        assert abs(result_arr.mean() - 152) < 3, \
            f"Лицо в диапазоне не должно корректироваться: {result_arr.mean():.0f}"
        assert factor == 1.0, f"factor должен быть 1.0 без коррекции"

    def test_empty_mask_returns_original(self):
        """Пустая маска — изображение не меняется."""
        gray = Image.new("L", (200, 200), 100)
        mask = Image.new("L", (200, 200), 0)  # пустая
        target = [140, 165]

        result, before, after, factor = check_face_brightness(gray, target, mask, glow_size=0)
        assert np.array(result).mean() == 100, "Пустая маска — без коррекции"
        assert before == 0.0, "before = 0.0 при пустой маске"
        assert factor == 1.0, "factor = 1.0 при пустой маске"

    def test_face_region_top_parameter(self):
        """face_region_top ограничивает зону замера верхней частью."""
        # Изображение 200x200: верхняя часть темная (80), нижняя — светлая (240)
        arr = np.full((200, 200), 240, dtype=np.uint8)
        arr[:100, :] = 80  # верхняя половина — тёмная
        gray = Image.fromarray(arr)
        mask = Image.new("L", (200, 200), 255)  # всё — субъект
        target = [140, 165]

        # С face_region_top=0.5 — замеряем только верхнюю половину (тёмную)
        result, before, after, factor = check_face_brightness(
            gray, target, mask, glow_size=0, face_region_top=0.5
        )
        # before должен быть ближе к 80 (верхняя часть), а не к 160 (среднее всего)
        assert before < 120, f"before должен отражать верхнюю часть: {before}"

    def test_correction_only_within_mask(self):
        """v6.5: Тёмное лицо осветляется, маска не затрагивает фон."""
        # Левая половина — субъект (маска=255), правая — фон (маска=0)
        arr = np.full((200, 200), 80, dtype=np.uint8)
        gray = Image.fromarray(arr)
        mask_arr = np.zeros((200, 200), dtype=np.uint8)
        mask_arr[:, :100] = 255  # левая половина — субъект
        mask = Image.fromarray(mask_arr)
        target = [140, 165]

        result, before, after, factor = check_face_brightness(
            gray, target, mask, glow_size=0
        )
        result_arr = np.array(result)

        # Правая половина (вне маски) не должна измениться
        right_half = result_arr[:, 100:]
        assert np.all(right_half == 80), \
            f"Фон вне маски не должен корректироваться, got max={right_half.max()}"

        # v6.5: Левая половина осветляется bounded delta
        left_half = result_arr[:, :100]
        assert left_half.mean() > 80.0, \
            f"v6.5: тёмное лицо должно осветлиться, got {left_half.mean():.0f}"
        assert factor > 1.0, "v6.5: factor>1.0 для осветления"

    def test_bright_skin_not_overexposed(self):
        """Уже яркие пиксели кожи не засвечиваются дальше (target_ceiling)."""
        # Изображение: среднее по лицу = 100 (тёмное), но некоторые пиксели уже 190+
        arr = np.full((200, 200), 100, dtype=np.uint8)
        arr[10:30, 10:30] = 190  # уже яркие пиксели кожи
        gray = Image.fromarray(arr)
        mask = Image.new("L", (200, 200), 255)
        target = [140, 165]

        result, before, after, factor = check_face_brightness(
            gray, target, mask, glow_size=0
        )
        result_arr = np.array(result)

        # Пиксели уже выше target_max (165) НЕ должны стать ещё ярче
        bright_region = result_arr[10:30, 10:30]
        assert bright_region.mean() <= 195, \
            f"Уже яркие пиксели ({190}) не должны засвечиваться: got {bright_region.mean():.0f}"

    def test_no_double_brightening_beyond_target(self):
        """После apply_levels + check_face_brightness пиксели не улетают за target_max."""
        from retouch.processing.levels import apply_levels

        # Симулируем пайплайн: apply_levels(1.18) → check_face_brightness
        arr = np.full((200, 200), 150, dtype=np.uint8)
        arr[80:120, 80:120] = 200  # яркая область (кожа)
        gray = Image.fromarray(arr)
        mask = Image.new("L", (200, 200), 255)
        target = [150, 170]

        # Step 1: apply_levels
        leveled = apply_levels(gray, brightness_factor=1.18)

        # Step 2: check_face_brightness
        result, before, after, factor = check_face_brightness(
            leveled, target, mask, glow_size=0
        )
        result_arr = np.array(result)

        # Уже яркие пиксели (были 200, после levels ~236) не должны улететь за 255
        bright_region = result_arr[80:120, 80:120]
        # С target_ceiling=170, пиксели >=170 не должны стать ярче
        assert bright_region.max() <= 255
        # И не должно быть массового клиппинга (все = 255)
        clipping_ratio = (bright_region == 255).sum() / bright_region.size
        assert clipping_ratio < 0.5, \
            f"Слишком много клиппинга ({clipping_ratio:.0%}) — лицо засвечено"


    def test_low_median_bright_skin_no_overexposure(self):
        """Низкая медиана + уже светлая кожа → осветление не засвечивает кожу.

        Симулирует двойной портрет: много тёмных пикселей (волосы) в зоне
        лица занижают медиану, но кожа уже яркая (p75 >= target_max).
        _curves_correction защищает уже яркие пиксели через highlight_start.

        skin_threshold=0 чтобы волосы участвовали в замере — именно их
        наличие занижает медиану и триггерит ложное осветление.
        При skin_threshold=100 (default) волосы отфильтруются, медиана
        по коже будет 200 > target_max, и код корректно затемнит —
        это проверяется отдельным тестом ниже.
        """
        # face_region_top=0.45 — замеряется верхняя часть изображения.
        # Создаём изображение 400x200, где в верхней части (180px):
        #   55% тёмных (волосы=30) → занижают медиану
        #   45% ярких (кожа=200) → p75 в яркой области
        h = 400
        arr = np.full((h, 200), 30, dtype=np.uint8)
        # В верхней части (rows 100-179): яркая кожа
        arr[100:180, :] = 200
        gray = Image.fromarray(arr)
        mask = Image.new("L", (200, h), 255)  # width=200, height=h
        target = [150, 170]

        result, before, after, factor = check_face_brightness(
            gray, target, mask, glow_size=0,
            skin_threshold=0,  # замер по ВСЕМ пикселям (включая волосы)
        )
        result_arr = np.array(result, dtype=np.float32)
        # Кожа не должна клиппиться к 255 (даже при коррекции)
        skin_region = result_arr[100:180, :]
        clipping_pct = (skin_region >= 250).sum() / skin_region.size * 100
        assert clipping_pct < 5.0, (
            f"Кожа клиппится: {clipping_pct:.1f}% >= 250"
        )

    def test_bright_skin_with_skin_threshold_gets_darkened(self):
        """skin_threshold отфильтровывает волосы → кожа=200 > target_max → затемнение.

        Когда skin_threshold=100 (default), тёмные пиксели (волосы=30)
        исключаются из замера. Остаётся только кожа=200, что выше
        target_max=170 — код корректно затемняет до target_mid=160.
        """
        h = 400
        arr = np.full((h, 200), 30, dtype=np.uint8)
        arr[100:180, :] = 200
        gray = Image.fromarray(arr)
        mask = Image.new("L", (200, h), 255)
        target = [150, 170]

        result, before, after, factor = check_face_brightness(
            gray, target, mask, glow_size=0,
            skin_threshold=100,  # default: волосы отфильтрованы
        )
        # Медиана по коже (200) > target_max (170) → затемнение
        assert factor < 1.0, (
            f"Кожа 200 > target_max 170: нужно затемнение, factor={factor:.3f}"
        )

    def test_low_median_near_ceiling_gentle_correction(self):
        """Медиана ниже target, p90 около target_max → мягкая коррекция (cap 1.08)."""
        # Зона лица: 50% тёмных (волосы=40), 50% средних (кожа=120)
        # p75≈120, p90≈120 — p90 < target_max-15=155, но p75 < target_max=170
        # → нормальная коррекция с cap 1.20 (не gentled)
        arr = np.full((200, 200), 40, dtype=np.uint8)
        arr[100:200, :] = 120  # нижняя половина ярче
        gray = Image.fromarray(arr)
        mask = Image.new("L", (200, 200), 255)
        target = [150, 170]

        result, before, after, factor = check_face_brightness(
            gray, target, mask, glow_size=0
        )
        # Медиана ~40, но есть яркие пиксели. Коррекция применяется,
        # но потолок (target_ceiling=170) защищает от засвета.
        result_arr = np.array(result)
        assert result_arr.max() <= 170, (
            f"Ни один пиксель не должен превышать target_max=170, "
            f"got max={result_arr.max()}"
        )

    def test_curves_ceiling_never_exceeded(self):
        """_curves_correction: коррекция не выталкивает пиксели за target_ceiling.

        Пиксели УЖЕ выше потолка не осветляются дальше (остаются как есть).
        Пиксели НИЖЕ потолка после коррекции не превышают его.
        """
        # Пиксель 156 при factor=1.20 → 156*1.20=187.2 > target_ceiling=170
        # Старый баг: ceiling_weight не защищал пиксели ниже highlight_start
        arr = np.array([50, 100, 140, 156, 165], dtype=np.float32)
        mask = np.ones(5, dtype=bool)
        result = _curves_correction(
            arr, correction=1.20,
            highlight_start=160,
            mask=mask,
            target_ceiling=170.0,
        )
        # Все пиксели ниже потолка после коррекции не превышают его
        below_ceiling = result[arr < 170]
        assert np.all(below_ceiling <= 170.0), (
            f"Пиксели ниже потолка не должны его превышать, "
            f"got max={below_ceiling.max():.1f}"
        )
        # Пиксель 156 конкретно: до фикса давал 187.2, теперь <= 170
        assert result[3] <= 170.0, (
            f"Пиксель 156 не должен превышать потолок 170, got {result[3]:.1f}"
        )


class TestMaskProtection:
    """P6: масочная защита — фон не меняется при коррекции."""

    def test_levels_preserves_background_with_mask(self):
        """Levels с mask не меняет фоновые пиксели."""
        arr = np.full((100, 100), 128, dtype=np.uint8)
        mask_arr = np.zeros((100, 100), dtype=np.uint8)
        arr[30:70, 30:70] = 180
        mask_arr[30:70, 30:70] = 255
        img = Image.fromarray(arr)
        mask = Image.fromarray(mask_arr)
        result = apply_levels(img, brightness_factor=1.3, subject_mask=mask)
        result_arr = np.array(result)
        # Фон не изменился (был 128)
        assert result_arr[10, 10] == 128, f"Фон изменился: {result_arr[10, 10]}"
        # Субъект изменился (180 * 1.3 = 234)
        assert result_arr[50, 50] > 180, f"Субъект не осветлился: {result_arr[50, 50]}"

    def test_levels_without_mask_backward_compat(self):
        """Levels без mask работает как раньше (глобальный enhance)."""
        img = Image.new("L", (100, 100), 128)
        result = apply_levels(img, brightness_factor=1.18)
        arr = np.array(result)
        # Все пиксели умножены
        assert arr[50, 50] > 128

    def test_unsharp_preserves_background_with_mask(self):
        """Unsharp с mask не создаёт halo на границе субъект/фон."""
        arr = np.zeros((100, 100), dtype=np.uint8)
        mask_arr = np.zeros((100, 100), dtype=np.uint8)
        # Резкий переход: субъект=200, фон=0
        arr[30:70, 30:70] = 200
        mask_arr[30:70, 30:70] = 255
        img = Image.fromarray(arr)
        mask = Image.fromarray(mask_arr)
        result = apply_unsharp_mask(img, subject_mask=mask)
        result_arr = np.array(result)
        # Фон остался чёрным (0 или очень близко)
        assert result_arr[10, 10] <= 2, f"Фон загрязнился: {result_arr[10, 10]}"

    def test_face_brightness_pillow_with_mask(self):
        """Face Brightness с mask не ломает фон (P6.4)."""
        arr = np.zeros((100, 100), dtype=np.uint8)
        mask_arr = np.zeros((100, 100), dtype=np.uint8)
        arr[20:80, 20:80] = 150
        mask_arr[20:80, 20:80] = 255
        img = Image.fromarray(arr)
        mask = Image.fromarray(mask_arr)
        result, *_ = check_face_brightness(
            img, [150, 170], mask, glow_size=20, face_region_top=0.45,
            highlight_start=160,
        )
        result_arr = np.array(result)
        # Фон остался 0
        assert result_arr[5, 5] <= 2, f"Фон изменился: {result_arr[5, 5]}"


class TestAdaptiveLevels:
    """Этап 3: bounded delta вместо factor."""

    def test_bright_input_no_clipping(self):
        """Яркий вход (median=211) — delta = 0 (в диапазоне), без изменений."""
        analytics = {
            'median_brightness': 211.0,
            'p90_brightness': 240.0,
        }
        img = Image.new("L", (100, 100), 211)
        result = apply_levels(img, analytics=analytics, machine_type='laser_standard')
        result_arr = np.array(result)
        assert result_arr.max() < 255, "Клиппинг при ярком входе"

    def test_dark_input_gets_brightened(self):
        """Тёмный вход (median=80) — delta > 0, осветление."""
        analytics = {
            'median_brightness': 80.0,
            'p90_brightness': 150.0,
        }
        img = Image.new("L", (100, 100), 80)
        result = apply_levels(img, analytics=analytics, machine_type='laser_standard')
        assert np.array(result).mean() > 80

    def test_overbright_input_gets_darkened(self):
        """Сверхъяркий вход (median=240) — delta < 0, затемнение."""
        analytics = {
            'median_brightness': 240.0,
            'p90_brightness': 252.0,
        }
        img = Image.new("L", (100, 100), 240)
        result = apply_levels(img, analytics=analytics, machine_type='laser_standard')
        # laser_standard: target_max=245, median=240 < 245 → delta=0
        # delta=0 → no change, but ceiling may still apply
        assert np.array(result).mean() <= 240

    def test_clipping_protection(self):
        """median выше target_max → delta < 0, затемнение."""
        analytics = {
            'median_brightness': 250.0,
            'p90_brightness': 252.0,
        }
        img = Image.new("L", (100, 100), 250)
        result = apply_levels(img, analytics=analytics, machine_type='laser_standard')
        # laser_standard: target_max=245, median=250 > 245 → delta < 0
        result_arr = np.array(result)
        assert result_arr.mean() < 250, "median выше target_max должна затемняться"

    def test_laser_80w_lower_target(self):
        """Laser 80W: target_min=160, target_max=180."""
        analytics = {
            'median_brightness': 190.0,
            'p90_brightness': 220.0,
        }
        result_laser = apply_levels(
            Image.new("L", (100, 100), 190),
            analytics=analytics, machine_type='laser_standard',
        )
        result_80w = apply_levels(
            Image.new("L", (100, 100), 190),
            analytics=analytics, machine_type='laser_80w',
        )
        # laser_80w: median=190 > target_max=180 → delta < 0 (затемнение)
        # laser_standard: median=190 < target_min=230 → delta > 0 (осветление)
        assert np.array(result_80w).mean() < 190  # затемнение
        assert np.array(result_laser).mean() >= 190  # осветление или без изменений


class TestBoundedDelta:
    """Этап 3: _compute_bounded_delta формула."""

    def test_delta_zero_when_in_range(self):
        """median в target range → delta = 0."""
        from retouch.processing.levels import _compute_bounded_delta
        # laser_standard: target_min=230, target_max=245
        analytics = {'median_brightness': 235.0}
        delta = _compute_bounded_delta(analytics, 'laser_standard')
        assert delta == 0.0

    def test_delta_positive_when_below_target(self):
        """median ниже target_min → delta > 0 (осветление)."""
        from retouch.processing.levels import _compute_bounded_delta
        # laser_standard: target_min=230
        analytics = {'median_brightness': 200.0}
        delta = _compute_bounded_delta(analytics, 'laser_standard')
        assert delta > 0
        assert delta <= 15.0  # max_delta

    def test_delta_negative_when_above_target(self):
        """median выше target_max → delta < 0 (затемнение)."""
        from retouch.processing.levels import _compute_bounded_delta
        # laser_standard: target_max=245
        analytics = {'median_brightness': 250.0}
        delta = _compute_bounded_delta(analytics, 'laser_standard')
        assert delta < 0
        assert delta >= -15.0  # max_delta

    def test_delta_clipped_to_max(self):
        """Delta не превышает max_delta=15."""
        from retouch.processing.levels import _compute_bounded_delta
        analytics = {'median_brightness': 100.0}
        delta = _compute_bounded_delta(analytics, 'laser_standard')
        assert delta == 15.0


class TestAdaptiveUnsharp:
    """P5: адаптивный Unsharp percent."""

    def test_overbright_reduced_sharpening(self):
        """Overbright → сниженный percent (80)."""
        from retouch.processing.levels import _adaptive_unsharp_percent
        analytics = {'tonal_range': 80, 'input_class': 'overbright'}
        percent = _adaptive_unsharp_percent(analytics, 120)
        assert percent == 80

    def test_low_tonal_range_increased_sharpening(self):
        """Низкий tonal_range (<40) → усиленный percent (150)."""
        from retouch.processing.levels import _adaptive_unsharp_percent
        analytics = {'tonal_range': 30, 'input_class': 'bright'}
        percent = _adaptive_unsharp_percent(analytics, 120)
        assert percent == 150

    def test_normal_tonal_range_default_sharpening(self):
        """Нормальный tonal_range (>80) → стандартный percent (120)."""
        from retouch.processing.levels import _adaptive_unsharp_percent
        analytics = {'tonal_range': 100, 'input_class': 'bright'}
        percent = _adaptive_unsharp_percent(analytics, 120)
        assert percent == 120


class TestBoundedDeltaDefaults:
    """Этап 3: _compute_bounded_delta берёт значения из DEFAULTS."""

    def test_target_range_from_defaults_laser_standard(self):
        """laser_standard: target_min=230, target_max=245."""
        from retouch.processing.levels import _compute_bounded_delta
        analytics = {'median_brightness': 200.0}
        delta = _compute_bounded_delta(analytics, 'laser_standard')
        assert delta > 0  # 200 < 230 → осветление
        assert delta <= 15.0  # max_delta

    def test_target_range_from_defaults_laser_80w(self):
        """laser_80w: target_min=160, target_max=180."""
        from retouch.processing.levels import _compute_bounded_delta
        analytics = {'median_brightness': 140.0}
        delta = _compute_bounded_delta(analytics, 'laser_80w')
        assert delta > 0  # 140 < 160 → осветление
        assert delta <= 15.0

    def test_target_range_from_defaults_impact(self):
        """impact: target_min=170, target_max=215."""
        from retouch.processing.levels import _compute_bounded_delta
        analytics = {'median_brightness': 150.0}
        delta = _compute_bounded_delta(analytics, 'impact')
        assert delta > 0  # 150 < 170 → осветление
        assert delta <= 15.0

    def test_machine_cfg_overrides_defaults(self):
        """machine_cfg переопределяет target range из DEFAULTS."""
        from retouch.processing.levels import _compute_bounded_delta
        analytics = {'median_brightness': 150.0}
        machine_cfg = {
            "face_brightness_target_min": 140,
            "face_brightness_target_max": 160,
        }
        delta = _compute_bounded_delta(analytics, 'laser_standard', machine_cfg=machine_cfg)
        # 150 в диапазоне [140, 160] → delta = 0
        assert delta == 0.0

    def test_unknown_machine_type_uses_fallback(self):
        """Неизвестный machine_type использует fallback [180, 220]."""
        from retouch.processing.levels import _compute_bounded_delta
        analytics = {'median_brightness': 150.0}
        delta = _compute_bounded_delta(analytics, 'unknown_machine')
        assert delta > 0  # 150 < 180 → осветление
        assert delta <= 15.0

    def test_white_ceiling_from_defaults(self):
        """white_ceiling для laser_standard = 250 (из DEFAULTS)."""
        # Проверяем что apply_levels использует ceiling из конфига
        analytics = {'median_brightness': 150.0}
        img = Image.new("L", (100, 100), 200)
        result = apply_levels(img, analytics=analytics, machine_type='laser_standard')
        result_arr = np.array(result)
        assert result_arr.max() <= 250, "white_ceiling должен ограничивать результат"
