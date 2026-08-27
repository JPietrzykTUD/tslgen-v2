#!/usr/bin/env bash
# Install what run_paper.sh needs on Ubuntu 24.04, and say what each thing gates.
#
#   sudo ./setup_ubuntu.sh              # everything below
#   sudo ./setup_ubuntu.sh --arrow      # ... and Apache's Arrow apt repository
#        ./setup_ubuntu.sh --check      # install nothing, just report
#
# Grouped by what is lost without it, because most of this is optional and a run
# that silently drops a question is worse than one that refuses to start:
#
#   required   the compiler, CMake and the analysis. Without these nothing runs.
#   accel      libaccel-config, which DML dlopens as `libaccel-config.so.1` to
#              enumerate work queues. Without it every DSA/IAA hardware submission
#              fails with an internal error whatever the range size, so Q3's
#              accelerator rows are failures rather than measurements -- which is
#              why run_paper.sh refuses rather than warns.
#   pinning    numactl, so parallel figures are one thread per physical core of one
#              NUMA node instead of a measurement of cross-node latency.
#   baselines  Q1's external sorts. TBB is the one worth installing: without it
#              CMake builds oneTBB from source, which works and takes a while.
#              Arrow is the baseline whose result cannot be dismissed, and Ubuntu's
#              own is usually old enough to matter -- see --arrow.
#
# Two things this script does NOT do, because they need decisions it should not
# make for you:
#
#   * configure the DSA/IAA work queues. Installing the library is not enough --
#     the device has to have enabled queues, and how they are shaped is a choice.
#     `accel-config list` shows what exists; see the note printed at the end.
#   * build Intel QPL, which the IAA detectors need. It is not packaged; clone
#     https://github.com/intel/qpl and point CMake at it.
set -euo pipefail

check_only="no"
want_arrow="no"
for argument in "$@"; do
  case "$argument" in
    --check) check_only="yes" ;;
    --arrow) want_arrow="yes" ;;
    -h|--help) sed -n '2,35p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $argument" >&2; exit 2 ;;
  esac
done

if [[ "$check_only" == "no" && "$(id -u)" -ne 0 ]]; then
  echo "installing needs root: sudo $0 $*" >&2
  exit 1
fi

# Ubuntu 24.04 is what this is written against. Other releases mostly work; the
# names that move are libaccel-config's and Arrow's, so say so rather than failing.
if [[ -r /etc/os-release ]]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  if [[ "${VERSION_ID:-}" != "24.04" ]]; then
    echo "note: written for Ubuntu 24.04, this is ${PRETTY_NAME:-unknown}."
    echo "      Package names for libaccel-config and Arrow are the ones that"
    echo "      differ between releases; the rest are stable."
    echo
  fi
fi

required=(
  build-essential      # a working toolchain, and make
  cmake                # 3.25+; 24.04 ships 3.28
  git                  # FetchContent clones ips4o, x86-simd-sort, TSL
  ninja-build          # optional generator, but much faster on this tree
  pkg-config
  clang                # 24.04 ships clang 18; the clang_bool style wants newer
  python3-pandas       # findings.py and report.py
)
accel=(
  libaccel-config1     # the library DML dlopens
  libaccel-config-dev  # headers, for anything linking it directly
  accel-config         # the CLI that lists and configures work queues
)
pinning=(
  numactl
  libnuma-dev
)
baselines=(
  libtbb-dev           # else CMake builds oneTBB from source
)

# Whether the thing a package provides is actually available, which is not always
# the same as whether dpkg installed it. pandas in particular is as likely to come
# from pip as from apt, and reporting it MISSING when `import pandas` works would
# send somebody installing a second copy.
have_package() {
  local package="$1"
  dpkg -s "$package" >/dev/null 2>&1 && return 0
  case "$package" in
    python3-pandas) python3 -c 'import pandas' >/dev/null 2>&1 && return 0 ;;
  esac
  return 1
}

report_group() {
  local label="$1"; shift
  printf '%s\n' "$label"
  local package
  for package in "$@"; do
    if have_package "$package"; then
      if dpkg -s "$package" >/dev/null 2>&1; then
        printf '  %-22s installed\n' "$package"
      else
        printf '  %-22s present (not via apt)\n' "$package"
      fi
    else
      printf '  %-22s MISSING\n' "$package"
    fi
  done
}

install_group() {
  local label="$1"; shift
  local missing=()
  local package
  for package in "$@"; do
    have_package "$package" || missing+=("$package")
  done
  if [[ ${#missing[@]} -eq 0 ]]; then
    echo "$label: already complete"
    return
  fi
  echo "$label: installing ${missing[*]}"
  # Not fatal: a name that moved between releases should not stop the rest. The
  # report at the end says what is still missing and what it costs.
  apt-get install -y "${missing[@]}" || {
    echo "  !! some of ${missing[*]} could not be installed; see the report below" >&2
  }
}

if [[ "$check_only" == "yes" ]]; then
  report_group "required (nothing runs without these)" "${required[@]}"
  report_group "accel (Q3's hardware rows)" "${accel[@]}"
  report_group "pinning (parallel figures)" "${pinning[@]}"
  report_group "baselines (Q1)" "${baselines[@]}"
else
  apt-get update
  install_group "required" "${required[@]}"
  install_group "accel" "${accel[@]}"
  install_group "pinning" "${pinning[@]}"
  install_group "baselines" "${baselines[@]}"

  if [[ "$want_arrow" == "yes" ]]; then
    # Apache's own repository, because Ubuntu's libarrow-dev lags and Q1 compares
    # against `arrow::compute::SortIndices`. Recent Arrow keeps the compute kernels
    # in their own library and CMake package, which is what libarrow-compute-dev is
    # -- and the absence of exactly that produced
    #   undefined reference to `arrow::compute::Initialize()'
    echo "arrow: adding Apache's repository"
    apt-get install -y ca-certificates lsb-release wget
    codename="$(lsb_release --codename --short)"
    wget -qO /tmp/apache-arrow-apt-source.deb \
      "https://apache.jfrog.io/artifactory/arrow/$(lsb_release --id --short \
        | tr 'A-Z' 'a-z')/apache-arrow-apt-source-latest-${codename}.deb"
    apt-get install -y /tmp/apache-arrow-apt-source.deb
    rm -f /tmp/apache-arrow-apt-source.deb
    apt-get update
    apt-get install -y libarrow-dev libarrow-compute-dev || {
      echo "  !! libarrow-compute-dev is not in this repository; on an Arrow old" >&2
      echo "     enough to keep compute inside libarrow that is correct and" >&2
      echo "     libarrow-dev alone is enough." >&2
      apt-get install -y libarrow-dev
    }
  fi
fi

echo
echo "=============================================================="
report_group "required (nothing runs without these)" "${required[@]}"
echo
report_group "accel (Q3's hardware rows)" "${accel[@]}"
echo
report_group "pinning (parallel figures)" "${pinning[@]}"
echo
report_group "baselines (Q1)" "${baselines[@]}"
echo

# The library being installed is necessary and not sufficient: DML resolves it by
# `dlopen("libaccel-config.so.1")`, so what matters is whether the loader finds
# that soname, and then whether the device has any enabled work queue.
echo "accelerator readiness"
if ldconfig -p 2>/dev/null | grep -q 'libaccel-config\.so\.1'; then
  echo "  libaccel-config.so.1     resolvable by dlopen"
else
  echo "  libaccel-config.so.1     NOT resolvable -- Q3's hardware rows will be"
  echo "                           refused. If it is installed under an unusual"
  echo "                           prefix, either run ldconfig or pass"
  echo "                           LD_LIBRARY_PATH=<dir> to run_paper.sh."
fi
for device in dsa iax; do
  if [[ -e "/dev/$device" ]]; then
    echo "  /dev/$device                 present"
  else
    echo "  /dev/$device                 absent -- that device's rows will be drops"
  fi
done
if command -v accel-config >/dev/null 2>&1; then
  # Counted per kind, because `grep -c '"state":"enabled"'` counts the *devices*
  # too and reported "6 enabled" on a host with three devices and three queues.
  # The two numbers say different things and only one of them is a work queue.
  counts="$(accel-config list 2>/dev/null | python3 -c '
import json, sys
try:
    devices = json.load(sys.stdin)
except Exception:
    print("0 0 0"); raise SystemExit(0)
dev = wq = usable = 0
for device in devices:
    if device.get("state") == "enabled":
        dev += 1
    for group in device.get("groups", []):
        for queue in group.get("grouped_workqueues", []):
            if queue.get("state") != "enabled":
                continue
            wq += 1
            if queue.get("type") == "user":
                usable += 1
print(dev, wq, usable)
' 2>/dev/null || echo "0 0 0")"
  read -r accel_devices accel_queues accel_usable <<< "$counts"
  if [[ "${accel_queues:-0}" -gt 0 ]]; then
    echo "  devices                  $accel_devices enabled"
    echo "  work queues              $accel_queues enabled, $accel_usable usable from userspace"
    accel-config list 2>/dev/null | python3 -c '
import json, sys
try:
    devices = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for device in devices:
    for group in device.get("groups", []):
        for wq in group.get("grouped_workqueues", []):
            if wq.get("state") != "enabled":
                continue
            kind = wq.get("type", "?")
            note = "" if kind == "user" else "   <-- not usable from userspace"
            print("    {:<9} type={:<7} mode={:<10} name={}{}".format(
                wq.get("dev", "?"), kind, wq.get("mode", "?"),
                wq.get("name", ""), note))
' 2>/dev/null || true
    # Enabled and user-type is still not enough: the queue is reached through a
    # device node, and those are group-restricted. This is the failure that looks
    # like something else entirely -- DML reports
    #   create_delta failed: error (internal; is libaccel-config installed?)
    # when it cannot *open* the queue, so a run by a user outside the group reads
    # as a missing package. Checked for the user who will actually measure, which
    # is not root when the run drops privileges (isolate_cpus.sh run does).
    # Every queue owned by an in-kernel driver is the case that looks ready and is
    # not: `accel-config list` shows enabled queues, the library loads, and there
    # is still no character device to submit through, because a kernel-type queue
    # belongs to something like iaa_crypto rather than to userspace.
    if [[ "${accel_usable:-0}" -eq 0 ]]; then
      echo "    !! none of these queues is type=user, so no /dev/dsa or /dev/iax" >&2
      echo "       node exists and nothing in userspace can submit to them. They" >&2
      echo "       belong to an in-kernel driver (iaa_crypto, dmaengine). One has" >&2
      echo "       to be handed over, e.g. for an IAA device iax1:" >&2
      echo "         sudo accel-config disable-wq iax1/wq1.0" >&2
      echo "         sudo accel-config config-wq iax1/wq1.0 --type=user \\" >&2
      echo "              --mode=dedicated --priority=1 --group-id=0 \\" >&2
      echo "              --name=cosort_rle --wq-size=<from list>" >&2
      echo "         sudo accel-config enable-wq iax1/wq1.0" >&2
      echo "       A *shared* queue additionally needs PASID, so the kernel wants" >&2
      echo "       intel_iommu=on,sm_on; dedicated queues do not. Repeat per" >&2
      echo "       device -- IAA devices are usually odd-numbered (iax1, iax3, ...)." >&2
      echo "       Then this check should show a type=user queue and a /dev/iax" >&2
      echo "       node, and that node still has to be readable by the measuring" >&2
      echo "       user." >&2
    fi
    target_user="${SUDO_USER:-$(id -un)}"
    for node in /dev/dsa/* /dev/iax/*; do
      [[ -e "$node" ]] || continue
      # Numeric ids too: a container often cannot resolve the group that owns an
      # accelerator queue, and "UNKNOWN" is not something a reader can act on.
      owner="$(stat -c '%U(%u):%G(%g) %a' "$node")"
      if sudo -u "$target_user" test -r "$node" && \
         sudo -u "$target_user" test -w "$node" 2>/dev/null; then
        echo "    $node  $owner  readable+writable by $target_user"
      else
        group="$(stat -c '%G' "$node")"
        [[ "$group" == "UNKNOWN" ]] && group="$(stat -c '%g' "$node")"
        echo "    $node  $owner  NOT accessible by $target_user" >&2
        echo "      That is what makes a hardware detector fail with an" >&2
        echo "      'internal' error that names libaccel-config. Fix it with" >&2
        echo "        sudo usermod -aG $group $target_user   # then log in again" >&2
        echo "      or run the measurement as root (isolate_cpus.sh run drops" >&2
        echo "      back to \$SUDO_USER, so sudo alone is not enough)." >&2
      fi
    done
  else
    echo "  work queues              none enabled. The library and the device are"
    echo "                           not enough: a queue has to be configured and"
    echo "                           started, e.g."
    echo "                             sudo accel-config load-config -c <config>.conf"
    echo "                             sudo accel-config enable-device dsa0"
    echo "                             sudo accel-config enable-wq dsa0/wq0.0"
    echo "                           Sample configurations ship with accel-config"
    echo "                           under /usr/share/accel-config/. Without an"
    echo "                           enabled queue, submissions fail the same way a"
    echo "                           missing library makes them fail."
  fi
else
  echo "  work queues              unknown (accel-config not installed)"
fi
echo
echo "not installed by this script, and why:"
echo "  Intel QPL   the IAA detectors need it and it is not packaged. Clone"
echo "              https://github.com/intel/qpl and point CMake at the build."
echo "  Arrow       pass --arrow to add Apache's repository; Ubuntu's own is"
echo "              usually old enough that Q1 measures a different Arrow than"
echo "              the other machine does."
