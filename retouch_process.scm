(define (retouch-process-order input-path output-path machine-type)
  (let* (
         (image (car (gimp-file-load RUN-NONINTERACTIVE input-path input-path)))
         (layer (car (gimp-image-get-active-layer image)))
         (height (car (gimp-image-height image)))
         (width (car (gimp-image-width image)))
         ;; Machine-dependent parameters
         (shrink-px (if (string=? machine-type "impact") 5 10))
         (feather-px (if (string=? machine-type "impact") 20 60))
         (fill-opacity (if (string=? machine-type "impact") 70 35))
         (levels-gamma (if (string=? machine-type "impact") 1.12 1.15))
         ;; Scalable vignette (params match config.yaml → vignette)
         ;; vertical_offset = 0.10  → v-offset = height * 0.10 = height / 10
         ;; vertical_diameter = 0.50 → v-diameter = height * 0.50 = height / 2
         ;; headroom = 0.60          → arch extends height*0.60 above v-diameter
         ;; horizontal_oversize = 0.20 → not used in GIMP (gimp-ellipse-select has no oversize)
         ;; blur/feather = 60px
         (v-offset (/ height 10))
         (v-diameter (/ height 2))
         (headroom (* height 0.6))
         (arch-bottom (- height v-offset))
         (arch-top (- arch-bottom v-diameter headroom))
        )

    ;; 1. Convert to RGB for processing if needed
    (gimp-image-convert-rgb image)

    ;; 2. Select Blue Background and Clear it
    (gimp-context-set-foreground '(0 0 255))
    (gimp-by-color-select layer '(0 0 255) 100 2 FALSE FALSE 0 FALSE)
    (gimp-edit-clear layer)
    (gimp-selection-none image)

    ;; 3. Add Inner Glow (machine-dependent)
    (gimp-image-select-item image 2 layer) ; Select alpha
    (gimp-selection-shrink image shrink-px)
    (gimp-selection-feather image feather-px)
    (gimp-context-set-foreground '(255 255 255))
    (gimp-edit-bucket-fill layer 0 0 fill-opacity 0 FALSE 0 0)
    (gimp-selection-none image)

    ;; 4. Convert to Grayscale
    (gimp-image-convert-grayscale image)

    ;; 5. Levels (machine-dependent gamma)
    (gimp-levels layer 0 0 255 levels-gamma 0 255)

    ;; 6. Unsharp Mask
    (plug-in-unsharp-mask RUN-NONINTERACTIVE image layer 1.5 1.2 0)

    ;; 7. Final Vignette (scalable arch — head stays visible)
    ;; Ellipse extends above image; only bottom corners fade to black
    (gimp-ellipse-select image 0 arch-top width (- arch-bottom arch-top) 2 TRUE TRUE 60)
    (gimp-selection-invert image)
    (gimp-context-set-background '(0 0 0))
    (gimp-edit-clear layer)
    (gimp-selection-none image)

    ;; 8. Export to TIFF
    (gimp-file-save RUN-NONINTERACTIVE image layer output-path output-path)
    (gimp-image-delete image)
  )
)
