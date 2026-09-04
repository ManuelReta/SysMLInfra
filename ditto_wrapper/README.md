# Ditto wrapper


## Deploy ditto using minikube 

Export zscaler cert as der.

What this is: Zscaler (DNV's security proxy) intercepts HTTPS connections in WSL, causing certificate validation failures. This fix installs the Zscaler Root CA certificate so WSL trusts the proxy.

Steps:

Export the Zscaler Root CA certificate from Windows (one-time setup):

Press Win+R and type certmgr.msc to open Certificate Manager (otherwise you can find it in windows start search)
Navigate to: Certificates > Trusted Root Certification Authorities > Certificates
Find and right-click the latest (last) "Zscaler Root CA" certificate
Select "Export" → use DER format → save as zscaler.crt, use default settings (e.g., to Downloads folder)


https://minikube.sigs.k8s.io/docs/handbook/untrusted_certs/

```
minikube start

helm install -n ditto --create-namespace my-ditto oci://registry-1.docker.io/eclipse/ditto --version <version> --wait
```
The local-values.yaml file has to be used and the mongodb is per default not enabled. 
```
helm upgrade \
  my-ditto \
  ./ \
  -n ditto \
  -f local-values.yaml --set mongodb.enabled=true \
  --wait
```
e.g <version> could be 4.6.0 (This is the helm chart version not ditto version which are not longer coupled).
