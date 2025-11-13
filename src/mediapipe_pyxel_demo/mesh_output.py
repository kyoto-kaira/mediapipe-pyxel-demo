import cv2
import mediapipe as mp
import argparse
import sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--camera-index",
        type=int,
        default=1,
        help="使用するカメラ番号（例: 0, 1, 2 ...）"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="mesh_output.png",
        help="出力画像ファイル名"
    )
    args = parser.parse_args()

    camera_index = args.camera_index
    output_path = args.output

    # カメラを開く
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"カメラ {camera_index} を開けませんでした。", file=sys.stderr)
        sys.exit(1)

    mp_face_mesh = mp.solutions.face_mesh
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles

    # 1枚だけフレームを取得して処理
    ret, frame = cap.read()
    cap.release()

    if not ret:
        print("フレームの取得に失敗しました。", file=sys.stderr)
        sys.exit(1)

    # BGR -> RGB に変換（MediaPipe は RGB 前提）
    rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # FaceMesh で推定
    with mp_face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,  # 目・唇まわりのランドマークを高精度で
        min_detection_confidence=0.5
    ) as face_mesh:
        results = face_mesh.process(rgb_image)

        if not results.multi_face_landmarks:
            print("顔メッシュが検出できませんでした。", file=sys.stderr)
            sys.exit(1)

        # 描画用にコピー
        annotated = frame.copy()

        for face_landmarks in results.multi_face_landmarks:
            mp_drawing.draw_landmarks(
                image=annotated,
                landmark_list=face_landmarks,
                connections=mp_face_mesh.FACEMESH_TESSELATION,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp_drawing_styles
                .get_default_face_mesh_tesselation_style()
            )
            # 輪郭なども描画したい場合は下を有効化
            mp_drawing.draw_landmarks(
                image=annotated,
                landmark_list=face_landmarks,
                connections=mp_face_mesh.FACEMESH_CONTOURS,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp_drawing_styles
                .get_default_face_mesh_contours_style()
            )

        # 画像として保存
        cv2.imwrite(output_path, annotated)
        print(f"メッシュ画像を {output_path} に保存しました。")

        # プレビュー表示（不要ならコメントアウト）
        cv2.imshow("Face Mesh", annotated)
        print("何かキーを押すとウィンドウを閉じます。")
        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()