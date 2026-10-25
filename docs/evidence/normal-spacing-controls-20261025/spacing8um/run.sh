source /usr/lib/openfoam/openfoam2412/etc/bashrc || exit 1
set -eu
blockMesh > log.blockMesh 2>&1
checkMesh -allTopology -meshQuality > log.topologyQuality 2>&1
checkMesh -allGeometry -allTopology > log.extended 2>&1
