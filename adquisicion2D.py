import cv2
import numpy as np
import os
import time

# --- 1. CONFIGURACIÓN DEL TABLERO ---
# Número de esquinas INTERIORES del tablero (ej: un tablero 10x7 tiene 9x6 esquinas interiores)
CHESSBOARD_SIZE = (9, 6) # (columnas, filas)

# Criterios para la detección y refinamiento de esquinas
criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

# --- 2. CONFIGURACIÓN PARA DETECCIÓN DE MOVIMIENTO Y ADQUISICIÓN ---
# Umbral de movimiento: Si el vector de traslación (tvec) cambia en más de este valor (mm), se considera movimiento.
# Ajusta este valor según qué tan sensible quieres que sea la detección de movimiento.
# Un valor más pequeño detectará movimientos sutiles.
MOVEMENT_THRESHOLD_MM = 1 # 10 mm = 1 cm de cambio en la posición
MIN_TIME_BETWEEN_CAPTURES_SEC = 1.0 # Mínimo tiempo en segundos entre capturas automáticas

# --- 3. CONFIGURAR LA ADQUISICIÓN DE VIDEO ---
cap = cv2.VideoCapture(0) # '0' para la cámara predeterminada

if not cap.isOpened():
    print("Error: No se pudo abrir la cámara. Asegúrate de que esté conectada y no en uso.")
    exit()

# Establecer resolución
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280) # Ejemplo de resolución
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720) # Ejemplo de resolución
print(f"Resolución actual de la cámara: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")


# --- 4. CONFIGURAR CARPETA DE SALIDA ---
output_dir = "imagenes_para_calibracion_auto"
os.makedirs(output_dir, exist_ok=True)
print(f"Las imágenes se guardarán en: {os.path.abspath(output_dir)}")

# --- 5. PREPARAR PUNTOS DEL OBJETO 3D PARA solvePnP (solo para estimar pose y detectar movimiento) ---
# No necesitamos SQUARE_SIZE_MM preciso para esto, solo una escala relativa. Usaremos 1.0.
objp_for_pose = np.zeros((CHESSBOARD_SIZE[0] * CHESSBOARD_SIZE[1], 3), np.float32)
objp_for_pose[:, :2] = np.mgrid[0:CHESSBOARD_SIZE[0], 0:CHESSBOARD_SIZE[1]].T.reshape(-1, 2) * 1.0

# Una matriz de cámara de identidad y distorsión cero para solvePnP si no tenemos calibración.
# Esto nos dará una estimación de pose relativa, suficiente para detectar movimiento.
# ¡IMPORTANTE! Estos NO son los parámetros de calibración reales.
dummy_mtx = np.eye(3, dtype=np.float32)
dummy_mtx[0,0] = dummy_mtx[1,1] = 800 # Valores iniciales estimados para una lente
dummy_mtx[0,2] = cap.get(cv2.CAP_PROP_FRAME_WIDTH) / 2
dummy_mtx[1,2] = cap.get(cv2.CAP_PROP_FRAME_HEIGHT) / 2
dummy_dist = np.zeros((4,1), dtype=np.float32)


# --- 6. VARIABLES DE ESTADO ---
image_count = 0
last_tvec = None # Almacena la traslación del frame anterior
last_capture_time = time.time() # Último momento en que se guardó una imagen

# --- 7. BUCLE PRINCIPAL DE ADQUISICIÓN ---
print("\nInstrucciones:")
print("  - Mueve el tablero de ajedrez frente a la cámara.")
print("  - Las imágenes se guardarán automáticamente cuando se detecte un movimiento significativo.")
print("  - Presiona 'q' para salir en cualquier momento.")

while(True):
    ret, frame = cap.read() # Captura un frame
    if not ret:
        print("Error al leer el frame. ¿La cámara sigue conectada?")
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    display_frame = frame.copy() # Hacemos una copia para dibujar sobre ella

    # Intenta encontrar las esquinas del tablero
    ret_corners, corners = cv2.findChessboardCorners(gray, CHESSBOARD_SIZE, None)

    if ret_corners == True:
        # Refina las esquinas para una mejor estimación de pose
        corners2 = cv2.cornerSubPix(gray, corners, (11,11), (-1,-1), criteria)
        
        # Estima la pose del tablero (rvec y tvec)
        _, rvec, tvec = cv2.solvePnP(objp_for_pose, corners2, dummy_mtx, dummy_dist, flags=cv2.SOLVEPNP_ITERATIVE)

        # Dibuja las esquinas detectadas en verde
        cv2.drawChessboardCorners(display_frame, CHESSBOARD_SIZE, corners2, ret_corners)
        cv2.putText(display_frame, f"Tablero DETECTADO! (Imgs: {image_count})", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)

        current_time = time.time()
        
        # Lógica para la captura automática:
        # 1. Ya se ha capturado al menos una imagen antes (last_tvec no es None)
        # 2. Ha pasado suficiente tiempo desde la última captura
        # 3. El tablero se ha movido significativamente
        if last_tvec is not None and \
           (current_time - last_capture_time > MIN_TIME_BETWEEN_CAPTURES_SEC):
            
            # Calcula la diferencia de traslación
            movement_diff = np.linalg.norm(tvec - last_tvec) # Norma Euclidiana
            
            if movement_diff > MOVEMENT_THRESHOLD_MM:
                image_count += 1
                filename = os.path.join(output_dir, f"calib_image_{image_count:03d}.jpg")
                cv2.imwrite(filename, frame) # Guarda el frame ORIGINAL (sin dibujos)
                print(f"Imagen '{filename}' guardada. Movimiento: {movement_diff:.2f} mm")
                last_capture_time = current_time # Reinicia el temporizador
                # Opcional: Pausa visual para ver la captura
                # cv2.imshow('Capturada!', frame)
                # cv2.waitKey(200) # Muestra por 200ms
        
        last_tvec = tvec # Actualiza la pose anterior

    else:
        cv2.putText(display_frame, f"Buscando tablero... (Imgs: {image_count})", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
        last_tvec = None # Resetea la pose si el tablero no es visible

    # Mostrar el conteo de imágenes guardadas
    cv2.putText(display_frame, f"Guardadas: {image_count}", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2, cv2.LINE_AA)


    # Mostrar el frame procesado
    cv2.imshow('Adquisicion Auto de Imagenes para Calibracion', display_frame)

    # --- Control de usuario ---
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break

# Liberar la cámara y cerrar ventanas
cap.release()
cv2.destroyAllWindows()

print(f"\nAdquisición de imágenes finalizada. Total de imágenes guardadas: {image_count}")
