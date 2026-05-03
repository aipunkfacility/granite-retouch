;; retouch_process.scm — GIMP Script-Fu для постобработки портретов
;;
;; Параметры виньетки передаются из run_gimp.py (который читает config.yaml).
;; Функция НЕ содержит захардкоженных значений виньетки.
;;
;; Сигнатура:
;;   (retouch-process-order input-path output-path machine-type
;;      vignette-v-offset vignette-v-diameter vignette-headroom
;;      vignette-h-oversize vignette-blur-radius)
;;
;; Все vignette-* — float (доли от размера изображения), кроме blur-radius (int, px).
;;
;; Разница станков:
;;   laser:  широкий мягкий glow (10/60px, 35%), gamma 1.05 (чуть ярче)
;;   impact: узкий яркий glow (3/15px, 75%), gamma 0.92 (темнее — ударный след шире)

(define (retouch-process-order input-path output-path machine-type
         vignette-v-offset vignette-v-diameter vignette-headroom
         vignette-h-oversize vignette-blur-radius)
  (let* (
         (image (car (gimp-file-load RUN-NONINTERACTIVE input-path input-path)))
         (layer (car (gimp-image-get-active-layer image)))
         (height (car (gimp-image-height image)))
         (width (car (gimp-image-width image)))
         ;; Machine-dependent parameters
         ;; laser: wide soft glow, slightly brighter
         ;; impact: narrow bright glow, darker (impact marks are wider/deeper)
         (shrink-px (if (string=? machine-type "impact") 3 10))
         (feather-px (if (string=? machine-type "impact") 15 60))
         (fill-opacity (if (string=? machine-type "impact") 75 35))
         (levels-gamma (if (string=? machine-type "impact") 0.92 1.05))
         ;; Vignette parameters (from config.yaml → vignette)
         (v-offset (* height vignette-v-offset))
         (v-diameter (* height vignette-v-diameter))
         (headroom (* height vignette-headroom))
         (arch-bottom (- height v-offset))
         (arch-top (- arch-bottom v-diameter headroom))
        )

    ;; 1. Convert to RGB for processing if needed (skip if already RGB)
    (if (not (= (car (gimp-image-base-type image)) RGB))
        (gimp-image-convert-rgb image))

    ;; 2. Select Blue Background and Clear it
    ;; Threshold 180 — широкий захват синего хромакея (включает не-чистый #0000FF)
    (gimp-context-set-foreground '(0 0 255))
    (gimp-by-color-select layer '(0 0 255) 180 2 FALSE FALSE 0 FALSE)
    (gimp-edit-clear layer)
    (gimp-selection-none image)

    ;; 3. Add Inner Glow (machine-dependent)
    ;; Select alpha channel of subject, shrink inward, feather, fill white
    (gimp-image-select-item image 2 layer) ; Select alpha
    (gimp-selection-shrink image shrink-px)
    (gimp-selection-feather image feather-px)
    (gimp-context-set-foreground '(255 255 255))
    (gimp-edit-bucket-fill layer 0 0 fill-opacity 0 FALSE 0 0)
    (gimp-selection-none image)

    ;; 4. Convert to Grayscale
    (gimp-image-convert-grayscale image)

    ;; 5. Levels (machine-dependent gamma)
    ;; gamma < 1.0 = darker (impact), gamma > 1.0 = brighter (laser)
    (gimp-levels layer 0 0 255 levels-gamma 0 255)

    ;; 6. Unsharp Mask
    (plug-in-unsharp-mask RUN-NONINTERACTIVE image layer 1.5 1.2 0)

    ;; 7. Final Vignette (scalable arch — head stays visible)
    ;; Ellipse extends above and beyond image; only bottom corners fade to black
    (gimp-ellipse-select image 0 arch-top width (- arch-bottom arch-top) 2 TRUE TRUE (round vignette-blur-radius))
    (gimp-selection-invert image)
    (gimp-context-set-background '(0 0 0))
    ;; gimp-edit-fill с BACKGROUND-FILL = чёрный (не gimp-edit-clear!)
    (gimp-edit-fill layer BACKGROUND-FILL)
    (gimp-selection-none image)

    ;; 8. Export to TIFF
    (gimp-file-save RUN-NONINTERACTIVE image layer output-path output-path)
    (gimp-image-delete image)
  )
)
