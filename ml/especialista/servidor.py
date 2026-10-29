"""O especialista ao vivo: carrega o LoRA uma vez e responde POST /analisa {"sistema", "entrada"} -> análise (JSON).
Só em 127.0.0.1; uma geração por vez (a placa é uma só; o rodada_sync manda até 6 lutas em paralelo e elas esperam).

    .venv/bin/python servidor.py lora-v4            # porta 8765
"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from gerar import carrega, gera

PORTA = 8765
TRAVA = threading.Lock()


def main() -> int:
    versao = sys.argv[1]
    model, tok = carrega(versao)

    class Pedido(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            try:
                corpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                msgs = [{"role": "system", "content": corpo["sistema"]}, {"role": "user", "content": corpo["entrada"]}]
                with TRAVA:
                    analise = gera(model, tok, msgs, guloso=True)
                resposta, codigo = {**analise, "_versao": versao}, 200
            except Exception as e:  # o cliente cai para a fila de motores de sempre
                resposta, codigo = {"erro": str(e)[:300]}, 500
            dados = json.dumps(resposta, ensure_ascii=False).encode()
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

        def log_message(self, *a) -> None:  # sem uma linha por pedido no journal
            pass

    print(f"especialista {versao} em 127.0.0.1:{PORTA}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORTA), Pedido).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
