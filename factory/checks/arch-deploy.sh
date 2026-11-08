#!/usr/bin/env bash
# arch-deploy checks per [ADR-0010]: helm lint and helm template | kubeconform for every chart.
source "$FACTORY_HUB/factory/checks/lib/common.sh"

shopt -s nullglob
charts=(charts/*/Chart.yaml)
if [ ${#charts[@]} -eq 0 ]; then
  echo "== no Helm chart yet (charts/*/Chart.yaml): nothing to check"
  exit 0
fi

command -v kubeconform >/dev/null || { echo "checks: kubeconform is missing. Install it once: brew install kubeconform" >&2; exit 1; }
for c in "${charts[@]}"; do
  dir=$(dirname "$c")
  step helm lint "$dir"
  for values in "$dir"/values.yaml "$dir"/values-*.yaml; do
    echo; echo "== helm template $dir -f $values | kubeconform"
    helm template arch "$dir" -f "$values" | kubeconform -strict -summary -ignore-missing-schemas
  done
done
