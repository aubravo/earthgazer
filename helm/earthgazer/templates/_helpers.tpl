{{/*
Expand the name of the chart.
*/}}
{{- define "earthgazer.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "earthgazer.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "earthgazer.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "earthgazer.labels" -}}
helm.sh/chart: {{ include "earthgazer.chart" . }}
{{ include "earthgazer.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "earthgazer.selectorLabels" -}}
app.kubernetes.io/name: {{ include "earthgazer.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "earthgazer.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "earthgazer.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Get the PostgreSQL host
*/}}
{{- define "earthgazer.postgresql.host" -}}
{{- if .Values.postgresql.enabled }}
{{- printf "%s-postgresql" (include "earthgazer.fullname" .) }}
{{- else }}
{{- required "A valid .Values.externalPostgresql.host is required" .Values.externalPostgresql.host }}
{{- end }}
{{- end }}

{{/*
Get the PostgreSQL port
*/}}
{{- define "earthgazer.postgresql.port" -}}
{{- if .Values.postgresql.enabled }}
{{- print "5432" }}
{{- else }}
{{- .Values.externalPostgresql.port | default 5432 }}
{{- end }}
{{- end }}

{{/*
Get the PostgreSQL database name
*/}}
{{- define "earthgazer.postgresql.database" -}}
{{- if .Values.postgresql.enabled }}
{{- .Values.postgresql.auth.database }}
{{- else }}
{{- required "A valid .Values.externalPostgresql.database is required" .Values.externalPostgresql.database }}
{{- end }}
{{- end }}

{{/*
Get the PostgreSQL username
*/}}
{{- define "earthgazer.postgresql.username" -}}
{{- if .Values.postgresql.enabled }}
{{- .Values.postgresql.auth.username }}
{{- else }}
{{- required "A valid .Values.externalPostgresql.username is required" .Values.externalPostgresql.username }}
{{- end }}
{{- end }}

{{/*
Get the PostgreSQL password secret name
*/}}
{{- define "earthgazer.postgresql.secretName" -}}
{{- if .Values.postgresql.enabled }}
{{- if .Values.postgresql.auth.existingSecret }}
{{- .Values.postgresql.auth.existingSecret }}
{{- else }}
{{- printf "%s-postgresql" (include "earthgazer.fullname" .) }}
{{- end }}
{{- else }}
{{- required "A valid .Values.externalPostgresql.existingSecret is required" .Values.externalPostgresql.existingSecret }}
{{- end }}
{{- end }}

{{/*
Get the Redis host
*/}}
{{- define "earthgazer.redis.host" -}}
{{- if .Values.redis.enabled }}
{{- printf "%s-redis" (include "earthgazer.fullname" .) }}
{{- else }}
{{- required "A valid .Values.externalRedis.host is required" .Values.externalRedis.host }}
{{- end }}
{{- end }}

{{/*
Get the Redis port
*/}}
{{- define "earthgazer.redis.port" -}}
{{- if .Values.redis.enabled }}
{{- print "6379" }}
{{- else }}
{{- .Values.externalRedis.port | default 6379 }}
{{- end }}
{{- end }}

{{/*
Get the Redis password secret name
*/}}
{{- define "earthgazer.redis.secretName" -}}
{{- if .Values.redis.enabled }}
{{- if .Values.redis.auth.existingSecret }}
{{- .Values.redis.auth.existingSecret }}
{{- else }}
{{- printf "%s-redis" (include "earthgazer.fullname" .) }}
{{- end }}
{{- else }}
{{- required "A valid .Values.externalRedis.existingSecret is required" .Values.externalRedis.existingSecret }}
{{- end }}
{{- end }}

{{/*
Get the PVC name for data storage
*/}}
{{- define "earthgazer.dataVolumeName" -}}
{{- if .Values.persistence.existingClaim }}
{{- .Values.persistence.existingClaim }}
{{- else }}
{{- printf "%s-data" (include "earthgazer.fullname" .) }}
{{- end }}
{{- end }}

{{/*
Return the appropriate apiVersion for HPA
*/}}
{{- define "earthgazer.hpa.apiVersion" -}}
{{- if .Capabilities.APIVersions.Has "autoscaling/v2" }}
{{- print "autoscaling/v2" }}
{{- else }}
{{- print "autoscaling/v2beta2" }}
{{- end }}
{{- end }}

{{/*
Docker image reference
*/}}
{{- define "earthgazer.image" -}}
{{- if .Values.image.registry }}
{{- printf "%s/%s:%s" .Values.image.registry .Values.image.repository (.Values.image.tag | default .Chart.AppVersion) }}
{{- else }}
{{- printf "%s:%s" .Values.image.repository (.Values.image.tag | default .Chart.AppVersion) }}
{{- end }}
{{- end }}
