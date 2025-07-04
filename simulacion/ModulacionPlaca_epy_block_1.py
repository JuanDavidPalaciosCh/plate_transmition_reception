#############################################################
# bits2img_id_csv – RX con dataset y CSV                    #
#############################################################

import cv2, csv, numpy as np
from pathlib import Path
from gnuradio import gr

class bits2img_id_csv(gr.basic_block):
    def __init__(self,
                 width=50,
                 height=40,
                 out_root="./dataset_rx_yolo",
                 show=True):

        super().__init__(name="bits2img_id_csv",
                         in_sig=[np.uint8],
                         out_sig=None)

        # --- imagen / cabecera ---
        self.w = int(width)
        self.h = int(height)
        self.expected = self.w * self.h
        self.header   = np.array([1,1,1,0,1,0,1,0,1], dtype=np.uint8)
        self.id_len   = 8
        self.buffer   = np.empty(0, dtype=np.uint8)
        self.show     = bool(show)

        # --- dataset en disco -----
        self.root     = Path(out_root)
        self.dir_img  = self.root / "autos_bw"
        self.dir_bits = self.root / "autos_bits"
        self.csv_path = self.root / "dataset_rx.csv"

        for d in (self.dir_img, self.dir_bits):
            d.mkdir(parents=True, exist_ok=True)
        if not self.csv_path.exists():
            with self.csv_path.open("w", newline="") as f:
                csv.writer(f).writerow(["num_auto", "bw_plate", "bits"])

        # --- contadores de réplica por auto ---
        self.rep_count = {}   # {id: next_rep_no}

    # ----------------------------------------------------------- #
    def _save_record(self, car_id: int, img_bw: np.ndarray, bits: np.ndarray):
        # siguiente réplica #
        rep_no = self.rep_count.get(car_id, 1)
        self.rep_count[car_id] = rep_no + 1

        stem = f"auto{car_id:03d}_rep{rep_no:02d}"
        img_path  = self.dir_img  / f"{stem}.png"
        bits_path = self.dir_bits / f"{stem}.npy"

        cv2.imwrite(str(img_path), img_bw)
        np.save(bits_path, bits.astype(np.uint8))

        # guardar CSV
        with self.csv_path.open("a", newline="") as f:
            csv.writer(f).writerow([car_id, str(img_path), bits.tolist()])

        print(f"📁 Guardado {stem}")

    # ----------------------------------------------------------- #
    def general_work(self, in_items, out_items):
        data = in_items[0]
        if len(data) == 0:
            return 0
        self.buffer = np.append(self.buffer, data)

        pkt_len = len(self.header) + self.id_len + self.expected
        while True:
            lim = len(self.buffer) - pkt_len
            if lim < 0:
                break

            sync_found = False
            for i in range(lim + 1):
                if np.array_equal(self.buffer[i:i+len(self.header)], self.header):
                    # zonas
                    start_id  = i + len(self.header)
                    start_img = start_id + self.id_len
                    end_img   = start_img + self.expected
                    if len(self.buffer) < end_img:
                        break  # espera más bits
                    # --- ID ---
                    id_bits = self.buffer[start_id:start_id+self.id_len]
                    car_id  = np.packbits(id_bits)[0]
                    # --- placa bits ---
                    plate_bits = self.buffer[start_img:end_img]
                    self.buffer = self.buffer[end_img:]  # descartar procesado
                    sync_found = True

                    # reconstruir imagen (1=blanco)
                    img_bw = (1 - plate_bits).astype(np.uint8).reshape(self.h, self.w) * 255

                    if self.show:
                        disp = img_bw.copy()
                        cv2.putText(disp, f"Auto {car_id:03d}", (2, 14),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, 255, 1, cv2.LINE_AA)
                        cv2.imshow("Placa RX", disp)
                        cv2.waitKey(1)

                    # --- guardar en dataset / CSV
                    self._save_record(car_id, img_bw, plate_bits)

                    break
            if not sync_found:
                # limitar tamaño de buffer
                if len(self.buffer) > 10 * pkt_len:
                    self.buffer = self.buffer[-10*pkt_len:]
                break

        self.consume(0, len(data))
        return 0

