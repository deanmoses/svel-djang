# Citation Source Types

How Pinbase should think about Citation Source types.

## What Citation Source Types drive

- how the citation is rendered to readers. Examples:
  - book: The Encyclopedia of Pinball. Richard Bueschel. p. 30.
  - video: Roger Sharpe interview. 04:12. [YouTube]
- which fields are shown on edit screens
- how to assist with and validate location input. Examples:
  - a video source might prompt with Timestamp
  - a book source might prompt with Page, Chapter, or Kindle location
  - a flyer source might prompt with Front or Back
  - a URL source may require and validate that it's a URL fragment ("#....")
- autocomplete search behavior. Examples:
  - books may match on author/title/ISBN
  - periodicals may match on publication + issue + article title
  - videos may match on channel/title/date
  - records may match on institution + accession number

## Citation Source Type Taxonomy

### What Wikipedia Teaches

Wikipedia's source type taxonomy comes mostly from its [Citation Style 1 templates](https://en.wikipedia.org/wiki/Help:Citation_Style_1):

| Wikipedia CS1 template | Covers                                         |
| ---------------------- | ---------------------------------------------- |
| `cite arXiv`           | arXiv preprints                                |
| `cite AV media`        | audio and visual media                         |
| `cite AV media notes`  | AV media liner notes                           |
| `cite bioRxiv`         | bioRxiv preprints                              |
| `cite book`            | books and chapters                             |
| `cite CiteSeerX`       | CiteSeerX papers                               |
| `cite conference`      | conference papers                              |
| `cite document`        | short, stand-alone, offline documents          |
| `cite encyclopedia`    | edited collections / encyclopedia entries      |
| `cite episode`         | radio or TV episodes                           |
| `cite interview`       | interviews                                     |
| `cite journal`         | academic journals                              |
| `cite magazine`        | magazines and periodicals                      |
| `cite mailing list`    | public mailing lists                           |
| `cite map`             | maps; usually published physical or atlas maps |
| `cite medRxiv`         | medRxiv preprints                              |
| `cite news`            | news articles; print/online news stories       |
| `cite newsgroup`       | online newsgroups                              |
| `cite podcast`         | podcasts                                       |
| `cite press release`   | press releases                                 |
| `cite report`          | formal institutional reports                   |
| `cite serial`          | audio or video serials                         |
| `cite sign`            | signs and plaques                              |
| `cite speech`          | speeches                                       |
| `cite SSRN`            | SSRN papers                                    |
| `cite tech report`     | technical reports                              |
| `cite thesis`          | theses                                         |
| `cite web`             | web sources not covered by the above           |

These templates are concrete and pragmatic; they don't try to model the world, like a formal bibliographic model would. Instead they exist because they need different:

- common fields
- display rules
- editor workflows

Wikipedia keeps a broad fallback: `cite web` exists for web sources not covered by more specific templates.

Basically, Wikipedia's citation source type model does the same job as ours must, and we should only diverge if we demonstrate a clear product need. We don't have to implement all source types in the first pass, but only as need is demonstrated.
