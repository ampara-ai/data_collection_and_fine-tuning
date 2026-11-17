#!/usr/bin/env bash
# Lanza desde el Mac el entrenamiento de H2 en VMs de Colab con la CLI de Google (https://github.com/googlecolab/google-colab-cli).
# Instalación (una vez):  uv tool install google-colab-cli   y luego   colab auth
#
# Uso (desde la raíz del repo de datos, con los cambios ya commiteados y subidos a GitHub; la VM clona ese commit):
#   bash entrenamiento/v2/colab/launch.sh                         # las seis corridas en UNA VM, una tras otra
#   PARALLEL=6 bash entrenamiento/v2/colab/launch.sh              # seis VMs a la vez, una corrida por VM (mismos créditos, ~6x menos tiempo)
#   PARALLEL=3 bash ...                                           # tres VMs con dos corridas cada una
#   RUNS="full_matched:42" bash entrenamiento/v2/colab/launch.sh  # solo una corrida (o varias separadas por espacio)
# Variables: PARALLEL (VMs; 1 por defecto), GPU (L4), POLL (segundos entre consultas), DRIVE_DIR (carpeta en Drive), DATA_COMMIT
#
# El entrenamiento corre en cada VM en segundo plano: si este terminal se cierra, las VMs siguen. Cada corrida terminada queda en
# Drive. Para ver el estado:   colab sessions ;  para liberar una VM (y dejar de gastar créditos):  colab stop -s ampara-h2-1
# NO PROBADO contra Colab real: confirma las opciones con `colab <comando> --help` antes de la primera corrida.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
PARALLEL="${PARALLEL:-1}"; GPU="${GPU:-L4}"; POLL="${POLL:-300}"
RUNS="${RUNS:-full_matched:42 full_matched:1 full_matched:2 naive:42 naive:1 naive:2}"
DRIVE_DIR="${DRIVE_DIR:-/content/drive/MyDrive/ampara_h2}"
command -v colab >/dev/null || { echo "Instala la CLI: uv tool install google-colab-cli" >&2; exit 1; }

# La VM clona el repo de datos desde GitHub: el commit debe estar subido y el árbol limpio (así la procedencia de cada corrida es exacta).
DATA_COMMIT="${DATA_COMMIT:-$(git -C "$REPO" rev-parse HEAD)}"
[ -z "$(git -C "$REPO" status --porcelain)" ] || { echo "El repo de datos tiene cambios sin commit; haz commit y push antes." >&2; exit 1; }
git -C "$REPO" branch -r --contains "$DATA_COMMIT" 2>/dev/null | grep -q . || { echo "El commit $DATA_COMMIT no está en GitHub; haz push." >&2; exit 1; }
echo "repo de datos en $DATA_COMMIT | VMs: $PARALLEL | corridas: $RUNS"

# Reparte las corridas entre las VMs (round-robin)
set -- $RUNS; N=$#; [ "$PARALLEL" -le "$N" ] || PARALLEL="$N"
k=0; while [ "$k" -lt "$PARALLEL" ]; do eval "GROUP_$k=''"; k=$((k+1)); done
i=0; for r in "$@"; do k=$((i % PARALLEL)); eval "GROUP_$k=\"\$GROUP_$k $r\""; i=$((i+1)); done

start_session() {  # $1 = índice
  local s="ampara-h2-$1" g; eval "g=\"\$GROUP_$1\""
  colab new -s "$s" --gpu "$GPU" || return 1
  colab drivemount -s "$s" || return 1                      # la primera vez pide autorizar en el navegador
  colab upload -s "$s" "$HERE/vm_h2_train.sh" /content/vm_h2_train.sh || return 1
  colab exec -s "$s" <<PY || return 1
import subprocess
subprocess.Popen("DATA_COMMIT='$DATA_COMMIT' RUNS='$g' DRIVE_DIR='$DRIVE_DIR' nohup bash /content/vm_h2_train.sh > /content/h2_driver.log 2>&1 &", shell=True)
print("lanzado: $g")
PY
}
k=0; while [ "$k" -lt "$PARALLEL" ]; do
  start_session "$k" || { echo "No se pudo iniciar la VM $k (¿límite de sesiones o GPU no disponible?). Las ya iniciadas siguen; detenlas con colab stop." >&2; exit 1; }
  k=$((k+1))
done

finished=""
while :; do
  sleep "$POLL"; pending=0; k=0
  while [ "$k" -lt "$PARALLEL" ]; do
    case " $finished " in *" $k "*) k=$((k+1)); continue ;; esac
    s="ampara-h2-$k"
    out="$(colab exec -s "$s" <<PY 2>&1
import glob, os, subprocess
print(open('/content/h2.status').read().strip())
logs = sorted(glob.glob('$DRIVE_DIR/logs/*_seed*.log'), key=os.path.getmtime)
if logs: print(subprocess.run(['tail', '-n', '1', logs[-1]], capture_output=True, text=True).stdout.strip())
PY
)"
    echo "[$(date +%H:%M)] VM $k: $out"
    case "$out" in
      *ALL_DONE*) colab stop -s "$s"; finished="$finished $k" ;;
      *FAILED*)   echo "VM $k falló; sigue viva para revisar el log (colab stop -s $s cuando termines)."; finished="$finished $k" ;;
      *)          pending=$((pending+1)) ;;
    esac
    k=$((k+1))
  done
  [ "$pending" -eq 0 ] && { echo "Todas las VMs terminaron. Revisa Drive: $DRIVE_DIR"; exit 0; }
done
