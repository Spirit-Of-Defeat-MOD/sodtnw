"""🎭 Self swap's worker ("FaceApp the portrait with itself"): runs inside Remini's environment (remini.py sets it up).

    python remini_swap.py <models dir> <gfpgan weights> <identity.png> <target.png> <out.png> [norestore]

The identity's face (the original portrait) is put onto the target's face (the portrait after ✨ Remini) with InsightFace's
inswapper_128 - the same models VisoMaster uses, run on the CPU with onnxruntime (any PC; an NVIDIA card is used when
there's one): RetinaFace (facexlib) finds the faces and their 5 points, ArcFace (w600k_r50) reads the identity, the
swapper redraws the face at 128 px, it's pasted back with a soft mask, then GFPGAN cleans it up. Prints "ok <faces> <out>"
or "error <message>"."""
import os
import sys
import warnings

warnings.filterwarnings("ignore")

import cv2
import numpy as np

ARCFACE_DST = np.array([[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366], [41.5493, 92.3655], [70.7299, 92.2041]],
					   dtype=np.float32)  # (where ArcFace wants the eyes, nose and mouth corners in a 112 px face)


def faces(det, img):
	"""[(5 points, box area)] biggest first."""
	found = det.detect_faces(img, 0.9)
	out = []
	for f in found if found is not None else []:
		f = np.asarray(f, dtype=np.float32)
		out.append((f[5:15].reshape(5, 2), (f[2] - f[0]) * (f[3] - f[1])))
	return sorted(out, key=lambda x: -x[1])


def align(img, kps, size):
	m, _ = cv2.estimateAffinePartial2D(kps, ARCFACE_DST * (size / 112.0), method=cv2.LMEDS)
	return cv2.warpAffine(img, m, (size, size), borderValue=0.0), m


def session(path):
	import onnxruntime as ort
	providers = [p for p in ("CUDAExecutionProvider", "DmlExecutionProvider") if p in ort.get_available_providers()] + ["CPUExecutionProvider"]
	return ort.InferenceSession(path, providers=providers)


def feed(sess, name, arr):
	t = next(i.type for i in sess.get_inputs() if i.name == name)
	return arr.astype(np.float16 if "float16" in t else np.float32)


def main():
	models, weights, ident_p, target_p, out_p = sys.argv[1:6]
	restore = "norestore" not in sys.argv[6:]
	import onnx
	import torch
	from facexlib.detection import init_detection_model
	device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
	det = init_detection_model("retinaface_resnet50", half=False, device=device, model_rootpath="gfpgan/weights")
	ident = cv2.imread(ident_p, cv2.IMREAD_COLOR)
	target_full = cv2.imread(target_p, cv2.IMREAD_UNCHANGED)
	if ident is None or target_full is None:
		raise ValueError("can't read the pictures")
	alpha = target_full[:, :, 3] if target_full.ndim == 3 and target_full.shape[2] == 4 else None
	target = target_full[:, :, :3] if target_full.ndim == 3 else cv2.cvtColor(target_full, cv2.COLOR_GRAY2BGR)
	src = faces(det, ident)
	if not src:
		raise ValueError("no face found in the original")
	tgt = faces(det, target)
	if not tgt:
		raise ValueError("no face found to swap")
	# ArcFace: who it is (RGB, -1..1, 112 px aligned)
	arc = session(os.path.join(models, "w600k_r50.onnx"))
	face112, _ = align(ident, src[0][0], 112)
	blob = (cv2.cvtColor(face112, cv2.COLOR_BGR2RGB).astype(np.float32) - 127.5) / 127.5
	emb = arc.run(None, {arc.get_inputs()[0].name: feed(arc, arc.get_inputs()[0].name, blob.transpose(2, 0, 1)[None])})[0].astype(np.float32).ravel()
	emb /= np.linalg.norm(emb)
	swap_path = os.path.join(models, "inswapper_128.fp16.onnx")
	emap = onnx.numpy_helper.to_array(onnx.load(swap_path).graph.initializer[-1]).astype(np.float32)
	latent = emb.reshape(1, -1) @ emap
	latent /= np.linalg.norm(latent)
	swapper = session(swap_path)
	result = target.astype(np.float32)
	for kps, _ in tgt[:1]:  # (the portrait's face: the biggest)
		face128, m = align(target, kps, 128)
		t = cv2.cvtColor(face128, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
		pred = swapper.run(None, {"target": feed(swapper, "target", t.transpose(2, 0, 1)[None]), "source": feed(swapper, "source", latent)})[0]
		fake = cv2.cvtColor((np.clip(pred[0].transpose(1, 2, 0).astype(np.float32), 0, 1) * 255), cv2.COLOR_RGB2BGR)
		# back onto the portrait with a soft mask (InsightFace's paste back)
		h, w = target.shape[:2]
		im = cv2.invertAffineTransform(m)
		fake_full = cv2.warpAffine(fake, im, (w, h), borderValue=0.0)
		mask = cv2.warpAffine(np.full((128, 128), 255, np.float32), im, (w, h), borderValue=0.0)
		mask[mask > 20] = 255
		ys, xs = np.where(mask == 255)
		size = int(np.sqrt((ys.max() - ys.min()) * (xs.max() - xs.min()))) if len(ys) else 64
		mask = cv2.erode(mask, np.ones((max(size // 10, 10),) * 2, np.uint8), iterations=1)
		k = max(size // 20, 5)
		mask = cv2.GaussianBlur(mask, (2 * k + 1, 2 * k + 1), 0)[:, :, None] / 255.0
		result = mask * fake_full + (1 - mask) * result
	out = np.clip(result, 0, 255).astype(np.uint8)
	if restore:  # (the swapper draws the face at 128 px: GFPGAN sharpens it back up)
		from gfpgan import GFPGANer
		g = GFPGANer(model_path=weights, upscale=1, arch="clean", channel_multiplier=2, bg_upsampler=None, device=device)
		_, _, restored = g.enhance(out, has_aligned=False, only_center_face=False, paste_back=True, weight=0.5)
		if restored is not None:
			out = restored
	if alpha is not None:
		out = np.dstack([out, cv2.resize(alpha, (out.shape[1], out.shape[0]))])
	cv2.imwrite(out_p, out)
	print(f"ok {len(tgt)} {out_p}", flush=True)


if __name__ == "__main__":
	try:
		import torch
		with torch.no_grad():  # (inference only: facexlib's detector fails otherwise)
			main()
	except Exception as ex:
		print(f"error {type(ex).__name__}: {ex}", flush=True)
