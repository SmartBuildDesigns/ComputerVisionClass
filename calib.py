import cv2
import numpy as np
import glob
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import os

# --- 1. CONFIGURACIÓN INICIAL ---
# Define el tamaño del tablero (número de esquinas interiores)
CHESSBOARD_SIZE = (9, 6) # (columnas, filas)
# Tamaño de cada cuadro del tablero en unidades reales (ej: milímetros o centímetros)
SQUARE_SIZE_MM = 25.0 # Por ejemplo, 25.0 mm por cuadro

# Criterios para la optimización de las esquinas (para cvFindCornerSubPix)
criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

# --- 2. PREPARAR PUNTOS DEL MUNDO REAL Y PUNTOS DE LA IMAGEN ---
objp = np.zeros((CHESSBOARD_SIZE[0] * CHESSBOARD_SIZE[1], 3), np.float32)
objp[:,:2] = np.mgrid[0:CHESSBOARD_SIZE[0], 0:CHESSBOARD_SIZE[1]].T.reshape(-1,2) * SQUARE_SIZE_MM

objpoints = [] # Puntos 3D
imgpoints = [] # Puntos 2D

# --- 3. DETECCIÓN Y REFINAMIENTO DE ESQUINAS ---
images = glob.glob('imagenes_para_calibracion_auto/*.jpg')

found_images = []

for fname in images:
    img = cv2.imread(fname)
    if img is None:
        print(f"Advertencia: No se pudo cargar la imagen {fname}. Saltando.")
        continue

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ret, corners = cv2.findChessboardCorners(gray, CHESSBOARD_SIZE, None)

    if ret == True:
        objpoints.append(objp)
        corners2 = cv2.cornerSubPix(gray, corners, (11,11), (-1,-1), criteria)
        imgpoints.append(corners2)
        found_images.append(fname)
        # No imprimimos aquí para no saturar la consola, se imprime el resumen al final
    # else:
    #    print(f"❌ Tablero NO detectado en: {os.path.basename(fname)}")

if not objpoints:
    print("Error: No se detectaron tableros en ninguna imagen. Asegúrate de que las imágenes sean correctas.")
    exit()

# --- 4. CALIBRACIÓN DE LA CÁMARA ---
h, w = gray.shape
ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
    objpoints,
    imgpoints,
    (w, h),
    None,
    None
)

print("\n--- RESULTADOS DE LA CALIBRACIÓN ---")
print("✅ Calibración Finalizada!")
print("\nMatriz Intrínseca (K):\n", mtx)
print("\nCoeficientes de Distorsión:\n", dist)
print("\nError de Reproyección Total (promedio):", ret)

# --- 5. GUARDAR PARÁMETROS DE CALIBRACIÓN ---
calib_filename = 'calibracion_camara.npz'
np.savez(calib_filename, mtx=mtx, dist=dist, rvecs=rvecs, tvecs=tvecs)
print(f"\nParámetros de calibración guardados en '{calib_filename}'")


# --- 6. VISUALIZACIÓN DE LA CORRECCIÓN DE DISTORSIÓN CON PUNTOS DE REPROYECCIÓN ---
if found_images:
    # Elegimos una imagen de prueba del conjunto de calibración (ej: la del medio)
    img_test_path = found_images[len(found_images) // 2]
    img_original = cv2.imread(img_test_path)
    if img_original is None:
        print(f"Error: No se pudo cargar la imagen de prueba {img_test_path}.")
        exit()

    gray_test = cv2.cvtColor(img_original, cv2.COLOR_BGR2GRAY)
    ret_test, corners_original = cv2.findChessboardCorners(gray_test, CHESSBOARD_SIZE, None)

    if ret_test:
        corners_original_refined = cv2.cornerSubPix(gray_test, corners_original, (11,11), (-1,-1), criteria)

        # Corregir la distorsión de la imagen
        mapx, mapy = cv2.initUndistortRectifyMap(mtx, dist, None, mtx, (w,h), 5)
        dst = cv2.remap(img_original.copy(), mapx, mapy, cv2.INTER_LINEAR) # Usar .copy() para no modificar el original

        # Calcular la pose de la cámara para esta imagen de prueba
        ret_pose, rvec_test, tvec_test = cv2.solvePnP(objp, corners_original_refined, mtx, dist)

        # Proyectar los puntos 3D del tablero (objp) de nuevo en la imagen
        # Esto nos da los puntos 2D corregidos (cómo deberían verse sin distorsión)
        imgpts_corrected, _ = cv2.projectPoints(objp, rvec_test, tvec_test, mtx, dist)
        
        # --- Dibujar en las imágenes ---
        # Dibujar las esquinas detectadas originalmente en la imagen original (distorsionada)
        img_with_original_corners = img_original.copy()
        cv2.drawChessboardCorners(img_with_original_corners, CHESSBOARD_SIZE, corners_original_refined, ret_test)
        
        # Dibujar los puntos corregidos (reproyectados) en la imagen corregida
        img_with_corrected_corners = dst.copy()
        # Dibujar círculos para los puntos corregidos
        for corner in imgpts_corrected:
            x, y = int(corner[0][0]), int(corner[0][1])
            cv2.circle(img_with_corrected_corners, (x, y), 5, (0, 255, 0), -1) # Círculos verdes
        # Opcional: Dibujar las líneas que unen estos puntos corregidos
        for i in range(CHESSBOARD_SIZE[1]): # Filas
            for j in range(CHESSBOARD_SIZE[0] - 1): # Columnas
                p1_idx = i * CHESSBOARD_SIZE[0] + j
                p2_idx = i * CHESSBOARD_SIZE[0] + j + 1
                p1 = tuple(imgpts_corrected[p1_idx][0].astype(int))
                p2 = tuple(imgpts_corrected[p2_idx][0].astype(int))
                cv2.line(img_with_corrected_corners, p1, p2, (0, 255, 255), 2) # Líneas horizontales (amarillas)
        for i in range(CHESSBOARD_SIZE[1] - 1): # Filas
            for j in range(CHESSBOARD_SIZE[0]): # Columnas
                p1_idx = i * CHESSBOARD_SIZE[0] + j
                p2_idx = (i + 1) * CHESSBOARD_SIZE[0] + j
                p1 = tuple(imgpts_corrected[p1_idx][0].astype(int))
                p2 = tuple(imgpts_corrected[p2_idx][0].astype(int))
                cv2.line(img_with_corrected_corners, p1, p2, (255, 0, 255), 2) # Líneas verticales (magenta)


        # Mostrar original y corregida lado a lado con las marcas
        plt.figure(figsize=(14, 7))
        plt.subplot(1, 2, 1)
        plt.imshow(cv2.cvtColor(img_with_original_corners, cv2.COLOR_BGR2RGB))
        plt.title('Original (Puntos detectados)')
        plt.axis('off')

        plt.subplot(1, 2, 2)
        plt.imshow(cv2.cvtColor(img_with_corrected_corners, cv2.COLOR_BGR2RGB))
        plt.title('Corregida (Puntos reproyectados)')
        plt.axis('off')
        plt.suptitle(f"Comparación de Distorsión y Reproyección (Imagen: {os.path.basename(img_test_path)})")
        plt.show()

        output_corrected_img = 'resultado_corregido_ejemplo_con_puntos.png'
        cv2.imwrite(output_corrected_img, img_with_corrected_corners)
        print(f"Imagen corregida de ejemplo con puntos guardada en '{output_corrected_img}'")

    else:
        print(f"Advertencia: No se pudo detectar el tablero en la imagen de prueba {img_test_path} para visualización detallada.")
else:
    print("\nNo hay imágenes para mostrar la corrección de distorsión.")


# --- 7. VISUALIZACIÓN 3D DE LAS POSES DEL TABLERO (Cámara en el origen) ---

fig = plt.figure(figsize=(10, 8))
ax = fig.add_subplot(111, projection='3d')

# Dibujar la cámara fija en el origen del sistema de coordenadas del mundo
ax.scatter(0, 0, 0, marker='o', color='purple', s=100, label='Cámara (Fija en Origen)')
ax.quiver(0, 0, 0, SQUARE_SIZE_MM, 0, 0, color='r', length=2*SQUARE_SIZE_MM, arrow_length_ratio=0.3) # Eje X de la cámara
ax.quiver(0, 0, 0, 0, SQUARE_SIZE_MM, 0, color='g', length=2*SQUARE_SIZE_MM, arrow_length_ratio=0.3) # Eje Y de la cámara
ax.quiver(0, 0, 0, 0, 0, SQUARE_SIZE_MM, color='b', length=2*SQUARE_SIZE_MM, arrow_length_ratio=0.3) # Eje Z de la cámara
ax.text(SQUARE_SIZE_MM*2.2, 0, 0, 'Cam X', color='r')
ax.text(0, SQUARE_SIZE_MM*2.2, 0, 'Cam Y', color='g')
ax.text(0, 0, SQUARE_SIZE_MM*2.2, 'Cam Z', color='b')


board_centers_x = []
board_centers_y = []
board_centers_z = []

for i in range(len(rvecs)):
    rvec = rvecs[i]
    tvec = tvecs[i]

    R_obj_to_cam, _ = cv2.Rodrigues(rvec)

    transformed_board_points = (R_obj_to_cam @ objp.T + tvec).T

    x_coords = transformed_board_points[:, 0]
    y_coords = transformed_board_points[:, 1]
    z_coords = transformed_board_points[:, 2]

    ax.plot_wireframe(x_coords.reshape(CHESSBOARD_SIZE[1], CHESSBOARD_SIZE[0]),
                      y_coords.reshape(CHESSBOARD_SIZE[1], CHESSBOARD_SIZE[0]),
                      z_coords.reshape(CHESSBOARD_SIZE[1], CHESSBOARD_SIZE[0]),
                      color='gray', alpha=0.7, label=f'Tablero {i+1}' if i == 0 else "")

    board_axes_origin = tvec.ravel()
    board_axes_x = (R_obj_to_cam @ np.array([[SQUARE_SIZE_MM*0.5],[0],[0]]) + tvec).ravel()
    board_axes_y = (R_obj_to_cam @ np.array([[0],[SQUARE_SIZE_MM*0.5],[0]]) + tvec).ravel()
    board_axes_z = (R_obj_to_cam @ np.array([[0],[0],[-SQUARE_SIZE_MM*0.5]]) + tvec).ravel()
    
    ax.quiver(board_axes_origin[0], board_axes_origin[1], board_axes_origin[2],
              board_axes_x[0]-board_axes_origin[0], board_axes_x[1]-board_axes_origin[1], board_axes_x[2]-board_axes_origin[2],
              color='r', length=SQUARE_SIZE_MM*0.5, arrow_length_ratio=0.3)
    ax.quiver(board_axes_origin[0], board_axes_origin[1], board_axes_origin[2],
              board_axes_y[0]-board_axes_origin[0], board_axes_y[1]-board_axes_origin[1], board_axes_y[2]-board_axes_origin[2],
              color='g', length=SQUARE_SIZE_MM*0.5, arrow_length_ratio=0.3)
    ax.quiver(board_axes_origin[0], board_axes_origin[1], board_axes_origin[2],
              board_axes_z[0]-board_axes_origin[0], board_axes_z[1]-board_axes_origin[1], board_axes_z[2]-board_axes_origin[2],
              color='b', length=SQUARE_SIZE_MM*0.5, arrow_length_ratio=0.3)
    
    board_centers_x.append(board_axes_origin[0])
    board_centers_y.append(board_axes_origin[1])
    board_centers_z.append(board_axes_origin[2])


ax.set_xlabel('X (mm)')
ax.set_ylabel('Y (mm)')
ax.set_zlabel('Z (mm)')
ax.set_title('Poses del Tablero respecto a la Cámara Fija')
ax.legend()

all_coords = []
if board_centers_x:
    all_coords.extend(board_centers_x)
    all_coords.extend(board_centers_y)
    all_coords.extend(board_centers_z)
    all_coords = np.array(all_coords)

    if all_coords.size > 0:
        max_range = np.array([np.max(all_coords)-np.min(all_coords)]).max() / 2.0
        mid_x = (np.max(board_centers_x)+np.min(board_centers_x)) / 2.0
        mid_y = (np.max(board_centers_y)+np.min(board_centers_y)) / 2.0
        mid_z = (np.max(board_centers_z)+np.min(board_centers_z)) / 2.0

        mid_x = (mid_x + 0) / 2
        mid_y = (mid_y + 0) / 2
        mid_z = (mid_z + 0) / 2

        ax.set_xlim(mid_x - max_range, mid_x + max_range)
        ax.set_ylim(mid_y - max_range, mid_y + max_range)
        ax.set_zlim(mid_z - max_range, mid_z + max_range)

plt.show()

print("\nVisualización 3D de las poses del tablero (cámara fija) completada.")