############################################################
#   rand_img_src.py – envía 1 imagen aleatoria por disparo #
############################################################
import csv, ast, time, random, numpy as np, pmt
from gnuradio import gr


class rand_img_src(gr.basic_block):
    """
    Puerto de entrada  : mensaje (trigger)  -> self.port_id("trigger")
    Puerto de salida   : stream  uint8
    Acción             : cada mensaje ≫ envía 1 paquete bits  +  ceros el resto
    """

    def __init__(
        self,
        csv_path="/home/jpalaciosch/Documents/UNAL/Septimo semestre/Comunicaciones/Proyecto final/dataset_yolo/dataset_yolo.csv",
        header_bits=[1, 0, 1, 0, 1, 0, 0, 0, 1, 1],
        max_pkt_rate=10,   # ≈ muestras/s de los paquetes (para relleno)
    ):
        gr.basic_block.__init__(
            self, name="rand_img_src", in_sig=None, out_sig=[np.uint8]
        )

        # ── carga CSV ────────────────────────────────────────────────
        self.bits_list = []
        with open(csv_path, newline="") as f:
            for row in csv.DictReader(f):
                bits = np.array(ast.literal_eval(row["bits"]), dtype=np.uint8)
                if bits.size == 2000:
                    self.bits_list.append((int(row["num_auto"]), bits))
        if not self.bits_list:
            raise RuntimeError("CSV vacío o corrupto")

        self.header   = np.array(header_bits, dtype=np.uint8)
        self.zero_buf = np.zeros(max_pkt_rate, dtype=np.uint8)

        # estado
        self.tx_queue = np.empty(0, dtype=np.uint8)   # bytes pendientes

        # ── puerto de disparo ────────────────────────────────────────
        self.message_port_register_in(pmt.intern("trigger"))
        self.set_msg_handler(pmt.intern("trigger"), self._on_trigger)

    # .................................................................
    def _on_trigger(self, _msg):
        """Elige imagen aleatoria y la pone en cola para transmitir una vez."""
        car_id, bits = random.choice(self.bits_list)
        id_bits = np.unpackbits(np.array([car_id], dtype=np.uint8))
        pkt = np.concatenate((self.header, id_bits, bits))
        self.tx_queue = np.concatenate((self.tx_queue, pkt))

    # .................................................................
    def general_work(self, in_items, out_items):
        out = out_items[0]
        n   = len(out)

        # ¿hay paquete pendiente?
        if self.tx_queue.size:
            n_copy = min(n, self.tx_queue.size)
            out[:n_copy] = self.tx_queue[:n_copy]
            self.tx_queue = self.tx_queue[n_copy:]
            return n_copy

        # si no, rellenamos con ceros para evitar underflow
        n_zero = min(n, self.zero_buf.size)
        out[:n_zero] = self.zero_buf[:n_zero]
        return n_zero

