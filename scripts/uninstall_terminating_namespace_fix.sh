#!/bin/bash
if [ -z $1 ]; then
  echo "please include a search string for \$1"
  exit 1
fi

ns=$(kubectl get namespaces | grep -oe "$1[^ ]*")

echo $ns

for n in $ns; do
  kubectl get namespace "$n" -o json --kubeconfig kube/config | tr -d "\n" | sed "s/\"finalizers\": \[[^]]\+\]/\"finalizers\": []/" | kubectl replace --kubeconfig kube/config --raw "/api/v1/namespaces/$n/finalize" -f -
done
