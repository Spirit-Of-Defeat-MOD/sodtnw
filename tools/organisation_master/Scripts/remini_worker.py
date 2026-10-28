"""✨ Remini's worker: runs inside the GFPGAN environment that remini.py sets up (not in Organisation Master itself).

    python remini_worker.py <weights.pth> <scale> <in.png> <out.png> [<in2.png> <out2.png> ...]
    python remini_worker.py <weights.pth> warmup        (loads everything once: facexlib fetches its face models)

GFPGAN (https://github.com/TencentARC/GFPGAN, Apache-2.0) finds the faces, restores them and pastes them back on the
picture upscaled <scale> times. A picture with transparency keeps it (its alpha is scaled to match). Prints one line
per picture: "ok <faces> <out>" or "error <message>"."""
import os
import sys
import warnings

warnings.filterwarnings("ignore")


def main():
	weights, what = sys.argv[1], sys.argv[2]
	import cv2
	import numpy as np
	import torch
	from gfpgan import GFPGANer
	scale = 2 if what == "warmup" else int(what)
	restorer = GFPGANer(model_path=weights, upscale=scale, arch="clean", channel_multiplier=2, bg_upsampler=None,
						device=torch.device("cuda" if torch.cuda.is_available() else "cpu"))
	if what == "warmup":
		img = np.full((256, 256, 3), 128, np.uint8)
		restorer.enhance(img, has_aligned=False, only_center_face=False, paste_back=True)
		print("ok warmup", "cuda" if torch.cuda.is_available() else "cpu", flush=True)
		return
	pairs = sys.argv[3:]
	for src, dst in zip(pairs[::2], pairs[1::2]):
		try:
			img = cv2.imread(src, cv2.IMREAD_UNCHANGED)
			if img is None:
				raise ValueError("can't read the picture")
			alpha = None
			if img.ndim == 3 and img.shape[2] == 4:
				alpha, img = img[:, :, 3], img[:, :, :3]
			elif img.ndim == 2:
				img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
			_, faces, out = restorer.enhance(img, has_aligned=False, only_center_face=False, paste_back=True)
			if out is None:
				raise ValueError("GFPGAN gave nothing back")
			if alpha is not None:
				a = cv2.resize(alpha, (out.shape[1], out.shape[0]), interpolation=cv2.INTER_LANCZOS4)
				out = np.dstack([out, a])
			os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
			cv2.imwrite(dst, out)
			print(f"ok {len(faces)} {dst}", flush=True)
		except Exception as ex:  # (one bad picture doesn't stop the rest)
			print(f"error {type(ex).__name__}: {ex}", flush=True)


if __name__ == "__main__":
	main()
