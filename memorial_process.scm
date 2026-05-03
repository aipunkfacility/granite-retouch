(define (memorial-process-order input-path output-path)
  (let* (
         (image (car (gimp-file-load RUN-NONINTERACTIVE input-path input-path)))
         (layer (car (gimp-image-get-active-layer image)))
        )
    
    ;; 1. Convert to RGB for processing if needed
    (gimp-image-convert-rgb image)
    
    ;; 2. Select Blue Background and Clear it (Step 2)
    (gimp-context-set-foreground '(0 0 255))
    (gimp-by-color-select layer '(0 0 255) 100 2 FALSE FALSE 0 FALSE)
    (gimp-edit-clear layer)
    (gimp-selection-none image)
    
    ;; 3. Add Inner Glow (Step 3)
    ;; Logic: Alpha to Selection, Shrink, Blur, Fill white
    (gimp-image-select-item image 2 layer) ; Select alpha
    (gimp-selection-shrink image 10) ; slightly inside
    (gimp-selection-feather image 60) ; blur edge
    (gimp-context-set-foreground '(255 255 255))
    (gimp-edit-bucket-fill layer 0 0 35 0 FALSE 0 0) ; fill white with 35% opacity
    (gimp-selection-none image)
    
    ;; 4. Convert to Grayscale (Step 1)
    (gimp-image-convert-grayscale image)
    
    ;; 5. Levels (Step 4)
    (gimp-levels layer 0 0 255 1.15 0 255) ; Gamma 1.15
    
    ;; 6. Unsharp Mask (Step 4)
    (plug-in-unsharp-mask RUN-NONINTERACTIVE image layer 1.5 1.2 0)
    
    ;; 7. Final Vignette (Arch)
    ;; Simple ellipse selection at bottom
    (gimp-ellipse-select image 0 (- (car (gimp-image-height image)) 400) (car (gimp-image-width image)) 800 2 TRUE TRUE 60)
    (gimp-selection-invert image)
    (gimp-context-set-background '(0 0 0))
    (gimp-edit-clear layer)
    (gimp-selection-none image)
    
    ;; 8. Export to TIFF
    (gimp-file-save RUN-NONINTERACTIVE image layer output-path output-path)
    (gimp-image-delete image)
  )
)
