# Offline site validation data

`public_suffix_list.dat` is the unmodified Mozilla Public Suffix List, including private entries,
downloaded2026-10-21 from https://publicsuffix.org/list/public_suffix_list.dat.
SHA256: `8228e4bdac6024c058a1e67859157e468a2613b826b53de0e5cae298e1b70755`.
Its original MPL2.0 notice is retained in the data header. This does not select a license for SubTrack.

`app.sites` uses exact, wildcard and exception rules offline to validate schemeful same-site sibling
origins. No runtime DNS lookup/network or new package is required. Refresh this data from the official
source during release maintenance, record the new hash/date, and rerun site/config tests. Operator
domain ownership, DNS and trusted certificates still require separate verification.
