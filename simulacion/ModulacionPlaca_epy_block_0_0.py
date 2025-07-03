import os, glob, cv2, numpy as np
from gnuradio import gr
import pmt

class img2bits(gr.basic_block):
    """
    Transmite N imágenes secuencialmente; cada una se repite `repeats` veces.

    Parameters
    ----------
    dir_path : str
        Carpeta que contiene las imágenes auto*.jpeg.
    repeats : int
        Número de veces que se enviará cada imagen.
    mode : {"bits", "int"}
        Igual que en tu versión original.
    """

    def __init__(self,
                 dir_path="/home/jpalaciosch/Documents/UNAL/Septimo semestre/Comunicaciones/Proyecto final/dataset/autos/",
                 repeats=10,
                 mode="bits"):
        self.mode    = mode.lower().strip()
        self.repeats = int(repeats)

        # ── Obtener lista de archivos ───────────────────────────────────────
        pattern = os.path.join(dir_path, "auto*.jp*g")  # acepta .jpeg o .jpg
        self.files = sorted(glob.glob(pattern))
        if not self.files:
            raise RuntimeError(f"No se encontraron imágenes con patrón {pattern}")

        # ── Señales de E/S ──────────────────────────────────────────────────
        out_sig = [np.uint8] if self.mode == "bits" else None
        gr.basic_block.__init__(self, name="img2bits_seq",
                                in_sig=None, out_sig=out_sig)

        # ── Cabecera fija ───────────────────────────────────────────────────
        self.header = np.array([1,1,1,0,1,0,1,0,1], dtype=np.uint8)

        # ── Estado interno ──────────────────────────────────────────────────
        self.file_idx   = 0          # índice en self.files
        self.repeat_left = self.repeats
        self._load_payload()         # crea self.payload y self.packet_len

        if self.mode == "int":
            self.message_port_register_out(pmt.intern("out"))

    # ------------------------------------------------------------------- #
    #  UTILIDADES                                                         #
    # ------------------------------------------------------------------- #
    def _extract_bits(self, path):
        """
        Recorta la placa, binariza y devuelve un vector 0/1 de longitud fija.
        (Mismo método que tenías, sin cambios funcionales).
        """
        img = cv2.imread(path)
        if img is None:
            raise RuntimeError(f"Imagen no encontrada: {path}")

        hsv  = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (20,100,100), (35,255,255))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                                cv2.getStructuringElement(cv2.MORPH_RECT, (5,5)))

        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        plate, possible, area_max = None, None, 0
        for c in cnts:
            x,y,w,h = cv2.boundingRect(c)
            r, area = w/float(h), w*h
            if 1.8 < r < 3.2 and w > 40:
                plate = img[y:y+h, x:x+w]; break
            elif area > area_max and w > 60:
                possible, area_max = img[y:y+h, x:x+w], area
        if plate is None and possible is not None:
            plate = possible
            print(f"⚠️  {os.path.basename(path)}: placa fuera de proporción ideal")

        if plate is None:
            print(f"No se detectó placa en {path}, rellenando...")
            return np.zeros(50 * 40, dtype=np.uint8)

        plate = cv2.resize(plate, (50, 40))
        gray  = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)
        _, bn = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)
        return (bn == 0).flatten().astype(np.uint8)

    def _load_payload(self):
        """Carga bits de la imagen actual y prepara self.payload / len."""
        actual_path   = self.files[self.file_idx]
        img_bits      = self._extract_bits(actual_path)
        self.payload  = np.concatenate((self.header, img_bits))
        self.packet_len = len(self.payload)

    def _advance_image(self):
        """Pasa a la siguiente imagen y resetea el contador de repeticiones."""
        self.file_idx += 1
        if self.file_idx >= len(self.files):
            self.file_idx = len(self.files)  # deja apuntando al final
            return False                     # ya no hay más imágenes
        self.repeat_left = self.repeats
        self._load_payload()
        return True

    # ------------------------------------------------------------------- #
    #  GNU RADIO                                                          #
    # ------------------------------------------------------------------- #
    def general_work(self, in_items, out_items):
        if self.mode != "bits":
            return 0

        out = out_items[0]
        if len(out) < self.packet_len:
            return 0  # el búfer aún no alcanza

        # ── Copiar paquete y etiquetar ───────────────────────────────────
        out[:self.packet_len] = self.payload
        self.add_item_tag(0, self.nitems_written(0),
                          pmt.intern("packet_len"),
                          pmt.from_long(self.packet_len))

        # ── ⬇️  mensaje de progreso  ⬇️ ───────────────────────────
        rep_no = self.repeats - self.repeat_left + 1          # 1..10
        img_no = self.file_idx + 1                            # 1..182
        print(f"Imagen {img_no:03d} mandada {rep_no}")
        # ────────────────────────────────────────────────────────────────

        # ── Gestionar recuento y paso a la siguiente ────────────────────
        self.repeat_left -= 1
        if self.repeat_left == 0:
            if not self._advance_image():     # sin más imágenes
                return -1                     # EOF → detener flujo

        return self.packet_len

    def start(self):
        """En modo 'int' publica cada paquete en un puerto de mensajes."""
        if self.mode == "int":
            packed = np.packbits(self.payload)
            value  = int.from_bytes(packed.tobytes(), "big")
            msg = pmt.cons(pmt.PMT_NIL,
                           pmt.from_uint64(value)
                           if value.bit_length() <= 64
                           else pmt.init_u8vector(len(packed), packed))
            self.message_port_pub(pmt.intern("out"), msg)
        return super().start()

