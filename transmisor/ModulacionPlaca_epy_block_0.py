import cv2
import numpy as np
from gnuradio import gr
import pmt

default_path = "/home/jpalaciosch/Documents/UNAL/Septimo semestre/Comunicaciones/Proyecto final/Img/auto1.jpeg"

class blk(gr.basic_block):
    def __init__(self, path=default_path, mode="bits"):
        self.mode = mode.lower().strip()
        out_sig = [np.uint8] if self.mode == "bits" else None

        gr.basic_block.__init__(self,
            name="img2bits",
            in_sig=None,
            out_sig=out_sig,
        )

        self.header = np.array([1, 1, 1, 0, 1, 0, 1, 0, 1], dtype=np.uint8)
        img_bits = self._extract_bits(path).astype(np.uint8)

        self.payload = np.concatenate((self.header, img_bits))
        self.packet_len = len(self.payload)
        self.index = 0

        if self.mode == "int":
            self.message_port_register_out(pmt.intern("out"))

    def _extract_bits(self, path, show=False):
        img = cv2.imread(path)
        if img is None:
            raise RuntimeError(f"Imagen no encontrada: {path}")

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (20, 100, 100), (35, 255, 255))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))

        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        plate = None
        possible_plate = None
        max_area = 0

        for c in cnts:
            x, y, w, h = cv2.boundingRect(c)
            r = w / float(h)
            area = w * h
            if 1.8 < r < 3.2 and w > 40:
                plate = img[y:y+h, x:x+w]
                break
            elif area > max_area and w > 60:
                possible_plate = img[y:y+h, x:x+w]
                max_area = area

        if plate is None and possible_plate is not None:
            plate = possible_plate
            print("⚠️ Usando placa con proporciones fuera de lo ideal")
        if plate is None:
            raise RuntimeError("No se encontró ninguna región que pueda ser una placa")

        plate = cv2.resize(plate, (45, 30))
        gray = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)
        _, bn = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)
        return (bn == 0).flatten()

    def general_work(self, in_items, out_items):
        if self.mode != "bits":
            return 0

        out = out_items[0]
        if len(out) < self.packet_len:
            return 0

        out[:self.packet_len] = self.payload
        self.add_item_tag(0, self.nitems_written(0), pmt.intern("packet_len"), pmt.from_long(self.packet_len))
        return self.packet_len

    def start(self):
        if self.mode == "int":
            packed = np.packbits(self.payload)
            value = int.from_bytes(packed.tobytes(), "big")
            msg = pmt.cons(pmt.PMT_NIL, pmt.from_uint64(value) if value.bit_length() <= 64 else pmt.init_u8vector(len(packed), packed))
            self.message_port_pub(pmt.intern("out"), msg)
        return super().start()

