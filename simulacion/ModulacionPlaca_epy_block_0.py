import os, csv, cv2, numpy as np
from pathlib import Path
from gnuradio import gr

class bits2dataset(gr.basic_block):
    """
    Reconstruye placas 45×30 desde un flujo de bits, las muestra y crea
    un dataset en disco + CSV donde se guarda *cada réplica*.

    CSV final:
        imagen,bits
        dataset_rx/autos/auto001_rep01.png,dataset_rx/autos_bits/auto001_rep01.npy
        dataset_rx/autos/auto001_rep02.png,dataset_rx/autos_bits/auto001_rep02.npy
        ...

    Parámetros
    ----------
    out_root : str   Carpeta destino del dataset.
    n_images : int  Cantidad de autos distintos (182).
    repeats  : int  Réplicas por auto (10).
    width,height :  dimensiones (45×30).
    show : bool     Mostrar ventana OpenCV.
    """

    def __init__(self,
                 out_root="./dataset_rx",
                 n_images=182,
                 repeats=10,
                 width=45,
                 height=30,
                 show=True):

        super().__init__(name="bits2dataset", in_sig=[np.uint8], out_sig=None)

        # ---- ajustes básicos ----
        self.width  = int(width)
        self.height = int(height)
        self.show   = bool(show)

        # ---- cabecera + longitudes ----
        self.expected = self.width * self.height
        self.header   = np.array([1,1,1,0,1,0,1,0,1], dtype=np.uint8)
        self.buffer   = np.empty(0, dtype=np.uint8)

        # ---- control de secuencia ----
        self.n_images     = int(n_images)
        self.repeats      = int(repeats)
        self.cur_img_idx  = 1         # auto actual (1..n_images)
        self.repeat_left  = self.repeats
        self.rep_no       = 1         # réplica actual (1..repeats)

        # ---- rutas ----
        self.root      = Path(out_root)
        self.dir_img   = self.root / "autos"
        self.dir_bits  = self.root / "autos_bits"
        self.csv_path  = self.root / "dataset_rx_index.csv"

        for d in (self.dir_img, self.dir_bits):
            d.mkdir(parents=True, exist_ok=True)
        if not self.csv_path.exists():
            with self.csv_path.open("w", newline="") as f:
                csv.writer(f).writerow(["imagen", "bits"])

    # ----------------------------------------------------------------- #
    def general_work(self, in_items, out_items):
        data = in_items[0]
        if len(data) == 0:
            return 0
        self.buffer = np.append(self.buffer, data)

        while True:
            limit = len(self.buffer) - len(self.header) - self.expected
            if limit < 0:
                break

            found = False
            for i in range(limit + 1):
                if np.array_equal(self.buffer[i:i+len(self.header)], self.header):
                    start = i + len(self.header); end = start + self.expected
                    if len(self.buffer) >= end:
                        frame = self.buffer[start:end]
                        self.buffer = self.buffer[end:]
                        self._save_frame(frame)        # ⬅️ guardar réplica
                        found = True
                        break
                    else:
                        break
            if not found:
                if len(self.buffer) > 10*(self.expected+len(self.header)):
                    self.buffer = self.buffer[-(self.expected+len(self.header)):]
                break

        self.consume(0, len(data))
        return 0

    # ----------------------------------------------------------------- #
    def _save_frame(self, bits):
        img = (1 - bits).astype(np.uint8).reshape(self.height, self.width)*255

        if self.show:
            cv2.imshow("RX placa", img)
            cv2.waitKey(1)

        # nombres con autoXXX_repYY
        stem = f"auto{self.cur_img_idx:03d}_rep{self.rep_no:02d}"
        img_path  = self.dir_img  / f"{stem}.png"
        bits_path = self.dir_bits / f"{stem}.npy"

        cv2.imwrite(str(img_path), img)
        np.save(bits_path, bits.astype(np.uint8))

        with self.csv_path.open("a", newline="") as f:
            csv.writer(f).writerow([str(img_path), str(bits_path)])

        print(f"📁 Guardado {stem}")

        # ---- actualizar contadores ----
        self.repeat_left -= 1
        self.rep_no      += 1
        if self.repeat_left == 0:
            self.cur_img_idx += 1
            self.repeat_left  = self.repeats
            self.rep_no       = 1
            if self.cur_img_idx > self.n_images:
                print("✅  Dataset completo.")

