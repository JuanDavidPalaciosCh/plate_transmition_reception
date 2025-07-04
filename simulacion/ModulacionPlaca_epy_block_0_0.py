############################################################
#   csv_bits_src.py  –  con ID del auto in‑band + tag       #
############################################################
import csv, ast, numpy as np, pmt
from gnuradio import gr

class csv_bits_src(gr.basic_block):

    def __init__(self,
                 csv_path="/home/jpalaciosch/Documents/UNAL/Septimo semestre/Comunicaciones/Proyecto final/dataset_yolo/dataset_yolo.csv",
                 repeats=10):

        # ---- parámetros generales ----
        self.repeats = int(repeats)
        self.header  = np.array([1,1,1,0,1,0,1,0,1], dtype=np.uint8)

        # ---- cargar CSV -------------------------------------------------
        self.bits_list = []   # [(id, bits), ...]
        with open(csv_path, newline="") as f:
            rdr = csv.DictReader(f)
            for row in rdr:
                bits = np.array(ast.literal_eval(row["bits"]), dtype=np.uint8)
                if bits.size != 2000:
                    print(f"⚠️  fila {row['num_auto']} tamaño {bits.size}")
                    continue
                car_id = int(row["num_auto"])  # 1..182
                if not (0 < car_id < 256):
                    print(f"⚠️  ID {car_id} fuera de rango 1‑255")
                    continue
                self.bits_list.append((car_id, bits))

        if not self.bits_list:
            raise RuntimeError("CSV sin bit‑arrays válidos.")

        # ---- estado interno --------------------------------------------
        self.row_idx     = 0
        self.repeat_left = self.repeats
        self._build_payload()

        gr.basic_block.__init__(self, name="csv_bits_src",
                                in_sig=None, out_sig=[np.uint8])

    # ------------------------------------------------------------------ #
    def _build_payload(self):
        car_id, bits = self.bits_list[self.row_idx]

        # 1 byte con el ID (uint8)
        id_byte   = np.array([car_id], dtype=np.uint8).view(np.uint8)
        # convertir byte→bits (8 bits MSB primero)
        id_bits   = np.unpackbits(id_byte)

        self.payload    = np.concatenate((self.header, id_bits, bits))
        self.packet_len = len(self.payload)
        self.cur_id     = car_id  # guarda para etiquetar

    def _next_row(self):
        self.row_idx += 1
        if self.row_idx >= len(self.bits_list):
            return False
        self.repeat_left = self.repeats
        self._build_payload()
        return True

    # ------------------------------------------------------------------ #
    def general_work(self, in_items, out_items):
        out = out_items[0]
        if len(out) < self.packet_len:
            return 0

        out[:self.packet_len] = self.payload

        # tag con longitud y con ID (opcional pero útil)
        offset = self.nitems_written(0)
        self.add_item_tag(0, offset,
                          pmt.intern("packet_len"),
                          pmt.from_long(self.packet_len))
        self.add_item_tag(0, offset,
                          pmt.intern("car_id"),
                          pmt.from_long(self.cur_id))

        # mensaje de progreso
        rep_idx = self.repeats - self.repeat_left + 1
        print(f"Auto {self.cur_id:03d}  réplica {rep_idx}")

        # administración de repeticiones
        self.repeat_left -= 1
        if self.repeat_left == 0:
            if not self._next_row():
                return -1
        return self.packet_len

