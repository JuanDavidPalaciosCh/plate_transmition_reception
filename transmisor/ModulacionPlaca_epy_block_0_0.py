############################################################
#   csv_bits_src.py  –  con relleno de ceros en la pausa    #
############################################################
import csv, ast, time, numpy as np, pmt
from gnuradio import gr


class csv_bits_src(gr.basic_block):
    def __init__(
        self,
        csv_path=(
            "/home/jpalaciosch/Documents/UNAL/Septimo semestre/Comunicaciones/"
            "Proyecto final/dataset_yolo/dataset_yolo.csv"
        ),
        repeats=10,
        pause_s=0.5,
    ):
        # ─── parámetros generales ───────────────────────────────────
        self.repeats  = int(repeats)
        self.pause_s  = pause_s
        self.header   = np.array([1, 0, 1, 0, 1, 0, 0, 0, 1, 1], dtype=np.uint8)

        # ─── cargar CSV ─────────────────────────────────────────────
        self.bits_list = []
        with open(csv_path, newline="") as f:
            for row in csv.DictReader(f):
                bits = np.array(ast.literal_eval(row["bits"]), dtype=np.uint8)
                if bits.size != 2000:
                    print(f"⚠️  fila {row['num_auto']} tamaño {bits.size}")
                    continue
                car_id = int(row["num_auto"])
                if not (0 < car_id < 256):
                    print(f"⚠️  ID {car_id} fuera de rango 1‑255")
                    continue
                self.bits_list.append((car_id, bits))

        if not self.bits_list:
            raise RuntimeError("CSV sin bit‑arrays válidos.")

        # ─── estado interno ─────────────────────────────────────────
        self.row_idx       = 0
        self.repeat_left   = self.repeats
        self._build_payload()

        # primer envío inmediato
        self.next_emit_t   = 0.0

        gr.basic_block.__init__(
            self, name="csv_bits_src", in_sig=None, out_sig=[np.uint8]
        )

    # ------------------------------------------------------------------
    def _build_payload(self):
        car_id, bits = self.bits_list[self.row_idx]
        id_bits      = np.unpackbits(np.array([car_id], dtype=np.uint8))
        self.payload     = np.concatenate((self.header, id_bits, bits))
        self.packet_len  = len(self.payload)
        self.cur_id      = car_id

    def _next_row(self):
        self.row_idx += 1
        if self.row_idx >= len(self.bits_list):
            return False
        self.repeat_left = self.repeats
        self._build_payload()
        return True

    # ------------------------------------------------------------------
    def general_work(self, in_items, out_items):
        out = out_items[0]
        now = time.time()

        # ≡≡ PAUSA: enviar ceros para evitar underflow ≡≡
        if now < self.next_emit_t:
            n = len(out)
            if n:                       # sólo si hay espacio en el búfer
                out[:n] = 0             # ceros lógicos
            return n                    # informar que llenamos n muestras

        # ≡≡ Enviar el paquete ≡≡
        if len(out) < self.packet_len:
            return 0                    # espera a tener búfer suficiente

        out[: self.packet_len] = self.payload

        # etiquetas
        offset = self.nitems_written(0)
        self.add_item_tag(0, offset, pmt.intern("packet_len"),
                          pmt.from_long(self.packet_len))
        self.add_item_tag(0, offset, pmt.intern("car_id"),
                          pmt.from_long(self.cur_id))

        # log
        rep_idx = self.repeats - self.repeat_left + 1
        print(f"Auto {self.cur_id:03d}  réplica {rep_idx}")

        # programa la próxima pausa
        self.next_emit_t = now + self.pause_s

        # administra repeticiones
        self.repeat_left -= 1
        if self.repeat_left == 0:
            if not self._next_row():
                return -1               # fin de archivo

        return self.packet_len

