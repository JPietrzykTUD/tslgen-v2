#!/usr/bin/env bash
# Make a set of CPUs exclusive to one measurement, on a cgroup v2 host.
#
#   sudo ./isolate_cpus.sh setup 0-5,12-17
#        ./isolate_cpus.sh status
#   sudo ./isolate_cpus.sh setup 0-5,12-17 --isolated   # only if you pin threads
#   sudo ./isolate_cpus.sh run  -- numactl --physcpubind=0-5 --membind=0 \
#                                 ./run_paper.sh --results results/$(hostname)
#   sudo ./isolate_cpus.sh reset
#
# Why this exists, rather than a line in a README:
#
# `numactl` and `taskset` decide where *this* process runs. They cannot stop the
# scheduler putting somebody else on the same cores -- that is a property of the
# cpuset, not of the process -- and on a shared machine that difference is the
# whole of whether a 4% result means anything.
#
# The usual advice for the exclusivity half is `cset shield`, and on a modern
# distribution it does not work: cset is a cgroup *v1* tool that mounts a cpuset
# filesystem at /cpusets, and a systemd host with the unified hierarchy has no v1
# cpuset to mount. The symptom is
#
#   mount: /cpusets: none already mounted or mount point busy.
#   cset: **> mount of cpuset filesystem failed, do you have permission?
#
# Check with `cat /proc/cgroups`: a `0` in the hierarchy column for cpuset means
# it lives on v2 and cset has nothing to work with.
#
# On v2 the mechanism is `cpuset.cpus.partition`, and *which value* matters more
# than it looks:
#
#   root      the CPUs become exclusive to this cgroup, and the scheduler still
#             load-balances across them.
#   isolated  exclusive as well, and load balancing is turned OFF -- the same state
#             `isolcpus=` produces at boot.
#
# `isolated` is the wrong one for a multithreaded benchmark, and getting this wrong
# cost a whole tuning run. With load balancing off the kernel does not spread
# threads across the partition: every worker the sort spawns inherits its creator's
# CPU and stays there. Six threads then share one core, which looks like
#
#   * htop showing a single busy core with six threads in the process,
#   * an aggregate near 100% instead of near 600%,
#   * and -- the part that matters -- six workers measuring *slower* than one, by a
#     uniform few percent, because they contend instead of dividing the work.
#
# The same tuner and the same shapes gave 2.87x (index quicksort) and 1.92x
# (samplesort) from one worker to six under a plain `taskset`, and 0.93x / 0.96x
# inside an `isolated` partition. Exclusivity was never the problem; load balancing
# was. So `root` is the default here, and `--isolated` exists for a caller who pins
# each thread itself.
#
# The same caveat applies to `isolcpus=<list>` at boot: it also removes those CPUs
# from the scheduling domains, so it wants per-thread pinning too. `nohz_full=` and
# `rcu_nocbs=` are the parts of a boot-time setup worth having on their own.
#
# Two more things make this fiddly enough to be worth a script: the order matters
# (cpus and mems before partition), and a failure reports itself by reading back as
# `... invalid` rather than by returning an error.
set -euo pipefail

root="/sys/fs/cgroup"
group="$root/tsl-measure"

usage() {
  sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

require_v2() {
  if ! mountpoint -q "$root" || [[ ! -f "$root/cgroup.controllers" ]]; then
    echo "no cgroup v2 unified hierarchy at $root" >&2
    exit 1
  fi
  if ! grep -qw cpuset "$root/cgroup.controllers"; then
    echo "the cpuset controller is not available in $root/cgroup.controllers" >&2
    echo "  on some distributions it has to be enabled: check the kernel's" >&2
    echo "  cgroup_no_v1= / systemd.unified_cgroup_hierarchy settings." >&2
    exit 1
  fi
}

setup() {
  local cpus="${1:?usage: setup <cpu-list>, e.g. 0-5,12-17}"
  shift || true
  # Load-balanced by default. See the note at the top: `isolated` stops the
  # scheduler spreading a sort's worker threads, which turns a parallel
  # measurement into six threads on one core.
  local mode="root"
  for argument in "$@"; do
    case "$argument" in
      --isolated) mode="isolated" ;;
      --root) mode="root" ;;
      *) echo "setup: unknown option $argument" >&2; exit 2 ;;
    esac
  done
  require_v2
  # The parent has to delegate cpuset before a child can use it.
  if ! grep -qw cpuset "$root/cgroup.subtree_control"; then
    echo "+cpuset" > "$root/cgroup.subtree_control"
  fi
  mkdir -p "$group"
  # Order matters: a partition cannot be formed until the cgroup has both a cpu
  # set and a memory node set. Writing partition first fails, and it fails by
  # reading back as invalid rather than by erroring.
  echo "$cpus" > "$group/cpuset.cpus"
  local mems
  mems="$(cat "$root/cpuset.mems.effective" 2>/dev/null || echo 0)"
  echo "$mems" > "$group/cpuset.mems"
  echo "$mode" > "$group/cpuset.cpus.partition"

  local state
  state="$(cat "$group/cpuset.cpus.partition")"
  if [[ "$state" != "$mode" ]]; then
    echo "the partition did not form: cpuset.cpus.partition reads '$state'" >&2
    echo "" >&2
    echo "  '$mode invalid' means the kernel would not give these CPUs up" >&2
    echo "  exclusively; the parenthesis above is its own reason. What each means:" >&2
    echo "" >&2
    echo "  'Parent is not a partition root' -- $root is itself only a member of" >&2
    echo "    somebody else's cgroup. On bare metal the real root is implicitly a" >&2
    echo "    partition root and this does not happen; inside a container it always" >&2
    echo "    does, because what looks like the root is a delegated subtree. There" >&2
    echo "    is no fix from in here: isolate on the host, or boot with isolcpus." >&2
    echo "    (this host's parent partition reads:" >&2
    echo "     $(cat "$root/cpuset.cpus.partition" 2>/dev/null || echo unknown))" >&2
    echo "  'invalid' for other reasons -- another cgroup already holds one of" >&2
    echo "    these CPUs as a partition, CPU 0 is in the list and the kernel" >&2
    echo "    refuses to isolate it, or the CPUs are not all in the parent's" >&2
    echo "    cpuset.cpus.effective" >&2
    echo "     ($(cat "$root/cpuset.cpus.effective" 2>/dev/null || echo unknown))." >&2
    echo "" >&2
    echo "  Nothing has been isolated. Run '$0 reset' to remove the group." >&2
    exit 1
  fi
  echo "exclusive: $cpus (partition=$mode)"
  echo "  the rest of the machine now sees: $(cat "$root/cpuset.cpus.effective")"
  if [[ "$mode" == "isolated" ]]; then
    echo "  !! load balancing is OFF in an isolated partition. Threads this run" >&2
    echo "     spawns will NOT be spread across these CPUs -- they inherit their" >&2
    echo "     creator's CPU. Pin them yourself, or use the default (root)." >&2
  else
    echo "  load balancing is on, so a sort's worker threads will spread"
  fi
  echo "  run a measurement inside it with: sudo $0 run -- <command>"
}

status() {
  if [[ ! -d "$group" ]]; then
    echo "no isolated group; the machine is whole"
    echo "  kernel-level isolation (isolcpus): ${_isolated:-$(cat /sys/devices/system/cpu/isolated 2>/dev/null)}"
    return
  fi
  echo "group          $group"
  echo "cpus           $(cat "$group/cpuset.cpus")"
  echo "partition      $(cat "$group/cpuset.cpus.partition")"
  echo "rest of host   $(cat "$root/cpuset.cpus.effective")"
  local procs
  procs="$(wc -l < "$group/cgroup.procs")"
  echo "processes      $procs"
}

run() {
  [[ "${1:-}" == "--" ]] && shift
  [[ $# -gt 0 ]] || { echo "usage: run -- <command>" >&2; exit 2; }
  if [[ ! -d "$group" ]]; then
    echo "nothing is isolated yet; run '$0 setup <cpu-list>' first" >&2
    exit 1
  fi
  # Join the cgroup, then drop back to the invoking user: the measurement writes
  # a results directory, and root-owned CSVs are a nuisance afterwards.
  echo $$ > "$group/cgroup.procs"
  if [[ -n "${SUDO_USER:-}" ]]; then
    exec setpriv --reuid "$SUDO_UID" --regid "$SUDO_GID" --init-groups "$@"
  fi
  exec "$@"
}

reset_group() {
  if [[ ! -d "$group" ]]; then
    echo "nothing to reset"
    return
  fi
  # Everything still inside has to leave before the group can go, and the
  # partition has to be dissolved before the CPUs return to the parent.
  if [[ -s "$group/cgroup.procs" ]]; then
    while read -r pid; do
      echo "$pid" > "$root/cgroup.procs" 2>/dev/null || true
    done < "$group/cgroup.procs"
  fi
  echo "member" > "$group/cpuset.cpus.partition" 2>/dev/null || true
  rmdir "$group"
  echo "released; the machine sees $(cat "$root/cpuset.cpus.effective")"
}

case "${1:-}" in
  setup) shift; setup "$@" ;;
  status) shift; status ;;
  run) shift; run "$@" ;;
  reset) shift; reset_group ;;
  -h|--help|"") usage 0 ;;
  *) echo "unknown command: $1" >&2; usage 2 ;;
esac
