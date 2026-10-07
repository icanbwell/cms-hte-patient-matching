# Data source licenses and terms of use

Every dataset committed under `data/institutional_registry/` (and the registry built from them,
`institutional_addresses.ndjson.gz`) comes from a third party. This doc records, per source, the
license or terms that govern reuse and redistribution, where that was read, and what the repo
must do to comply. Where a source's terms are restrictive or unconfirmed, the status says so.

**Reviewed 2026-10-07.** Source URLs and download dates are in
`data/institutional_registry/manifest.json`. Background is in
`docs/INSTITUTIONAL_ADDRESS_FEASIBILITY.md`; per-state coverage is in
`docs/ASSISTED_LIVING_STATE_COVERAGE.md`.

## How this was determined, and its limits

- Terms were read from each source's public pages: dataset or item metadata (license, access
  constraints), then the portal's terms, then the agency's website terms.
- Pages were fetched through an automated summariser, so quotes are near-verbatim, not raw page
  text. Several agency pages returned HTTP 403 or 404 and could not be read; those are marked.
  Items marked "search snippet" were not confirmed on the primary page.
- **This is not legal advice and has not had legal review.** Before relying on a row for
  redistribution, confirm the quoted terms on the live page.
- A "public record" status means the data is a government licensing list with no reuse terms
  found. It is not an explicit grant of redistribution rights.

## Status key

| Status | Meaning |
|---|---|
| **Open** | An explicit open license, or a public-domain / government-works statement. |
| **Open, attribution** | Open license that requires credit. |
| **Public record** | No reuse, redistribution or scraping terms found. |
| **Conditional** | Copying allowed under stated conditions (attribution, noncommercial, unaltered). |
| **Restrictive** | Terms prohibit or limit copying and redistribution without permission. |
| **Unresolved** | Terms could not be read or confirmed. |

## National sources

| Source (registry file) | Terms | Evidence | Status | Required action |
|---|---|---|---|---|
| HIFLD Prison Boundaries (`hifld_prisons.csv`) | US Government Works; public access; no use constraints stated. The HIFLD Next catalog we download from (`hifld.publicenvirodata.org`) carries no license field of its own, hence "other" in the archive metadata. | `catalog.data.gov/dataset/prison-boundaries` license field `https://www.usa.gov/government-works` | Open | None. The data.gov record is the basis; HIFLD Next is a third-party republisher with no terms found. |
| Overture Maps Places (`overture_gq.csv`) | Per contributing source: Meta, Microsoft, PinMeTo, Krick, RenderSEO, DAC, BrightQuery are CDLA Permissive 2.0 (attribution required); Foursquare is Apache 2.0 (attribution and notice required); AllThePlaces is CC0. | `docs.overturemaps.org/attribution/` | Open, attribution | Include the CDLA Permissive 2.0 text, per-source attribution and the Foursquare notice, and note that Foursquare data was transformed to the Overture schema. The per-source split is from Overture's documentation; which sources the downloaded extract draws on was not checked. |
| Princeton assisted-living dataset (`assisted_living.csv`) | CC BY 4.0, as stated in the repo's source documentation. | Dataset repository `antonstengel/assisted-living-data` (not re-checked in this review) | Open, attribution | Credit the dataset and link CC BY 4.0. Verify the license on the repository before citing it. |
| Prison Policy Initiative facility lists (`ppi_facilities.csv`) | No license or terms on the list page or the data toolbox. The only stated license (Creative Commons ShareAlike) covers their illustrations, not the data. The toolbox links a Reprint Policy that was not fetched. | `prisonersofthecensus.org/data/state_federal_local_2020vintage.html`; `prisonpolicy.org/data/` | Unresolved | No terms stated means all rights reserved by default. Request written permission from the publisher, or remove the file and keep the fetch script. The lists add only 888 addresses HIFLD lacks. |
| CMS Care Compare and Provider of Services (`care_compare_*.csv`, `pos_iqies.csv.gz`) | No license or attribution terms stated on the pages read. CMS describes its public data as "freely available on CMS' open data websites". Public domain by rule: federal employees' works are "not subject to domestic copyright protection under 17 U.S.C. § 105". A search snippet says CMS releases data under an open license; not confirmed on a primary page. | `cms.gov/data-research/cms-data/data-available-everyone`; `resources.data.gov/open-licenses/` | Open (by rule) | None required. Provider-submitted facility details could in principle carry their own rights; the risk is low and not a stated guarantee. |
| NCES IPEDS (`ipeds_hd.csv`) | No IPEDS-specific license found. IES site statement: "Unless otherwise stated, all content on the IES website is in the public domain and may be reproduced and linked without permission, provided this citation is used: U.S. Department of Education. Institute of Education Sciences." That covers website content, not the data files specifically. | `nces.ed.gov/about/public-access-research`; `resources.data.gov/open-licenses/` | Open (by rule) | Cite "U.S. Department of Education. Institute of Education Sciences." as the source. |
| Federal Bureau of Prisons locations (`bop.json`) | No copyright, reuse or terms statement found; the BOP privacy policy has none, and no BOP terms-of-use page was located. Presumed public domain as federal government works. The file is built from BOP website location pages, not a published dataset. | `bop.gov/website/privacy_policy.jsp`; `resources.data.gov/open-licenses/` | Open (by rule) | None required; nothing is stated either way. |

## State lists

Each state's file is `data/institutional_registry/state_lists/<ST>.csv`, except CA, FL, MI and WI,
which are the raw `state_al_*` files. Sources and methods are in
`docs/ASSISTED_LIVING_STATE_COVERAGE.md`.

### Open

| State | Terms | Evidence | Required action |
|---|---|---|---|
| CO | Item license text: "There are no restrictions and legal prerequisites for using this data set." Not a named license such as CC0. | CDPHE ArcGIS item info (`CDPHE_Health_Facilities`) | None. |
| NY | OPEN-NY terms: "You are welcome to freely download and use this Content as long as you abide by these Terms of Use"; no attribution or pre-approval requirement. | `data.ny.gov/download/77gx-ii52/application/pdf` (terms, modified 2013-03-08) | None. Dataset `wssx-idhx` was retired 2022-01-15 per its metadata; confirm it is still the intended source. |
| PA | Dataset license: Public Domain U.S. Government (`USGOV_WORKS`). | `data.pa.gov/api/views/pqf4-d4xn.json` | None. |
| UT | UGRC licenses its data under CC BY 4.0 unless a dataset's metadata says otherwise; this layer's metadata does not. | `gis.utah.gov/documentation/policy/license/` | Credit UGRC, link CC BY 4.0, note changes. |
| CA | CDSS site: information "is considered in the public domain... It may be distributed or copied as permitted by law." Site-level statement, not a dataset license; the dataset is hosted on the CHHS portal, whose terms page showed no license text. | `cdss.ca.gov/conditions-of-use` | None beyond confirming the CHHS portal terms. |
| NJ | State legal page: "anyone may view, copy or distribute State information found here without obligation to the State, unless otherwise stated on particular material." Site-wide, not a dataset license. | `nj.gov/nj/legal.shtml` | None. |

### Public record, no terms stated

| State | Notes |
|---|---|
| AZ | The ADHS ArcGIS item's license field holds only a no-warranty disclaimer; no copyright text. Agency site copyright notice is site-wide. |
| FL | AHCA disclaimer and copyright footer only; no reuse terms. Weaker: Florida public-records law was not checked. |
| GA | DCH legal notice cites the Open Records Act; no copying policy; the facility-search page has no terms. |
| IA | `iowa.gov/policies` says content posted to the state site is public information. That is the main state site, not the DIAL site; no license for the CSV export found. |
| MD | Socrata dataset `i48m-922u` has no license field; state site terms cover linking and framing only. The dataset appears to mirror a MD iMAP layer and is not clearly an OHCQ dataset; confirm provenance. |
| MN | MDH privacy page: information collected "becomes public record". That sentence concerns site-visitor data, not the provider list. No reuse or scraping terms found. |
| MO | Socrata dataset `fenu-sipv` has no license, attribution or terms fields set. Portal-wide terms not read. |
| NV | No terms on the vendor-hosted licensee search; footers are vendor and state copyright boilerplate. Weaker: the search is vendor-hosted. |
| OK | ArcGIS item has empty license and access fields. OSDH's own terms page returned 404; a sister agency's "public domain" notice was seen only in a search snippet. |
| OR | State site terms have no reuse or scraping prohibition. Adult foster home names are not carried (they are mostly licensees' personal names). |
| WI | Layer metadata gives only a copyright credit to the department; no license or access constraint. A portal-wide fair-use clause appeared only in a search snippet. Layers 17 and 2 were not checked individually. |
| WV | `wv.gov` legal notices are warranty and liability disclaimers; the link policy bars framing. No reuse restriction found. |

### Conditional

| State | Terms | Evidence | Required action |
|---|---|---|---|
| TN | Information "may be copied so long as it is presented in a non-misleading way"; credit the originating agency with its web address; do not imply state endorsement. The facility-listings page itself returned 403. | `tn.gov/web-policies/linking-policy.html` | Add agency credit and URL. |
| TX | HHSC asserts copyright; copying allowed for noncommercial or nonprofit use if content is unaltered, no endorsement is implied, a no-endorsement disclaimer is included, and HHSC is credited with web address and copy date. | `hhs.texas.gov/policies-practices-privacy` | Credit and disclaimer. "Unaltered" and "noncommercial" must be decided: the registry transforms the data. Applying this website policy to the directory file is an inference; no dataset-specific terms were found. |
| NC | DHSR disclaimer permits copying and sharing "for noncommercial purposes, provided the materials remain unaltered" (paraphrase by the summariser). | `info.ncdhhs.gov/dhsr/disclaim.html` | Decide whether committed files meet "unaltered"; byte-identical copies are the safest reading. |

### Restrictive

| State | Terms | Evidence | Required action |
|---|---|---|---|
| IN | Site terms (verbatim, read on the live page): "Except as may otherwise be allowed by law (including but not limited to the Indiana Access to Public Records Law), the viewing, printing, or downloading of any content, graphic, form, or document from the Portal grants you only a limited, nonexclusive license for use solely by you for your own personal use, and not for republication, distribution, assignment, sublicense, sale, preparation of derivative works or other use. No part of any content, graphic, form, or document may be reproduced in any form or incorporated into any information retrieval system, electronic or mechanical, other than for your personal use (not for resale or redistribution). You must keep intact all copyright and other proprietary notices. IN.gov may revoke this license at any time." | `in.gov/core/terms_of_use.html` | Redistribution in a public repo is outside the stated license. Request permission, or obtain the list through an Access to Public Records Act request and confirm what reuse that allows; otherwise remove the file and keep the fetch script. Whether the ISDH directory page is covered by these Portal terms or by the public-records carve-out is a legal question. |
| SC | DPH website policy: content is copyrighted; no reproducing or distributing any part of the site except as permitted by DPH in writing. Whether this covers the separately hosted ArcGIS layer is unclear; the layer's own metadata is empty. The restriction wording is paraphrased. | `dph.sc.gov/about/accessibility-nondiscrimination-privacy-notices/website-accessibility-and-policies` | Request written permission or remove the file. |
| VA | VDSS web policy: "You may use content under fair use"; other uses need written permission. | `dss.virginia.gov/general-info/web-policy/` | Bulk redistribution is probably beyond fair use; request permission or remove the file. |
| KY | General Commonwealth copyright, "fair use" only. Search snippet only; the primary page failed to load and the CHFS policy pages returned 404. | `ky.gov/kystandards/statements/copyright.html` (unread) | Confirm on the live page; request permission if it applies. |
| MI | Search snippet only: no commercial use or resale of website data without a written agreement, and no access "through any automated means (including use of scripts, web crawlers or screen scrapers)". The michigan.gov terms pages returned 403, and whether they cover the LARA document host is unconfirmed. | `michigan.gov/en/about/terms-of-use` (unread) | Confirm in a browser; request permission if it applies. |

### Unresolved

| State | What is known | Required action |
|---|---|---|
| AK | No terms on the source page; the footer asserts State copyright. A search snippet attributed to other Alaska agencies says republishing distributed documents needs department approval; unverified for the health department. | Ask the department's webmaster, or remove the file. |
| LA | All LDH terms pages returned 403. A search snippet shows only a no-liability notice. | Read the terms in a browser. |
| MA | MassGIS layer has empty license and copyright fields; the MassGIS terms page rendered only a heading. A search snippet says attribution is appreciated but not required. The layer data is dated 2023. | Read the terms in a browser. |
| NE | The ArcGIS layer has empty license and constraint fields. State portal terms found on another agency's site say copying is for personal, noncommercial use and bar redistribution and use of scrapers; whether they govern this layer is unconfirmed. | Confirm which terms apply; request permission if they do. |

## Attribution to carry in distributions

- **Overture Maps Places:** CDLA Permissive 2.0 text; per-source attribution for Meta, Microsoft,
  PinMeTo, Krick, RenderSEO, DAC and BrightQuery; the Apache 2.0 notice for Foursquare, noting
  the data was transformed to the Overture schema.
- **Princeton assisted-living dataset:** CC BY 4.0 credit and license link.
- **UT (UGRC):** CC BY 4.0 credit to UGRC, license link, and a note of any changes.
- **TN and TX:** agency credit with web address; for TX also the copy date and a no-endorsement
  disclaimer.

## Open decisions

1. Prison Policy Initiative: permission request, or removal.
2. Restrictive and unresolved state lists (IN, SC, VA, KY, MI, AK, LA, MA, NE): permission,
   removal, or a decision to accept the risk.
3. TX and NC "unaltered, noncommercial" conditions: whether the committed files and the registry
   comply.
4. CMS, IPEDS and BOP: public domain by the federal government-works rule, with no
   source-specific license stated. Confirm that is acceptable, and cite IES for IPEDS.
5. Legal review of this table before the registry is distributed outside the organization.

Removing a source means deleting its file and rebuilding the registry; the build is described in
`docs/INSTITUTIONAL_ADDRESS_FEASIBILITY.md`.
