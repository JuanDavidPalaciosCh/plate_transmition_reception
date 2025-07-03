#############################################################
#  bits2img – reconstruye imagen 45×30 desde un paquete     #
#  de bits (uchar 0/1) y la muestra con OpenCV              #
#############################################################

import cv2
import numpy as np
from gnuradio import gr

class blk(gr.basic_block):
    def __init__(self, width=45, height=30, show=True):
        gr.basic_block.__init__(self,
            name="bits2img",
            in_sig=[np.uint8],
            out_sig=None,
        )
        self.width = int(width)
        self.height = int(height)
        self.show = bool(show)

        self.expected = self.width * self.height
        self.header = np.array([1, 1, 1, 0, 1, 0, 1, 0, 1], dtype=np.uint8)
        self.buffer = np.empty(0, dtype=np.uint8)

    def general_work(self, in_items, out_items):
        inp = in_items[0]
        nread = len(inp)

        if nread == 0:
            return 0

        self.buffer = np.append(self.buffer, inp)

        while True:
            search_limit = len(self.buffer) - len(self.header) - self.expected
            if search_limit < 0:
                break

            found = False
            for i in range(search_limit + 1):
                if np.array_equal(self.buffer[i:i + len(self.header)], self.header):
                    start = i + len(self.header)
                    end = start + self.expected
                    if len(self.buffer) >= end:
                        frame_bits = self.buffer[start:end]
                        self.buffer = self.buffer[end:]  # quitar todo hasta fin del paquete
                        img = (1 - frame_bits).astype(np.uint8) * 255
                        img = img.reshape(self.height, self.width)
                        if self.show:
                            cv2.imshow("Imagen reconstruida", img)
                            cv2.waitKey(1)
                        found = True
                        break
                    else:
                        break  # esperar más datos

            if not found:
                # No encontramos header válido: eliminar parte frontal para evitar overflow
                if len(self.buffer) > 10 * (self.expected + len(self.header)):
                    self.buffer = self.buffer[-(self.expected + len(self.header)):]
                break

        self.consume(0, nread)
        return 0

