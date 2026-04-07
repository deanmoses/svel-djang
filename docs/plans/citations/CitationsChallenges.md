# Citations - Product Challenges

These are design constraints and product hazards that should stay front-of-mind while designing the citations feature.

## Citation systems impose too much complexity at the moment of authoring

That is a recurring product failure mode:

- Wikimedia's own research on [Citoid support for Wikimedia references](https://meta.wikimedia.org/wiki/Research:Citoid_support_for_Wikimedia_references) describes references as an intricate system that is difficult for inexperienced or non-technical users to add correctly.
- The [Wikimedia Usability Initiative study](https://usability.wikimedia.org/wiki/Usability%2C_Experience%2C_and_Evaluation_Study) likewise found that adding references was one of the more challenging editing tasks.
- Wikimedia's later [Reusing references research](https://meta.wikimedia.org/wiki/WMDE_Technical_Wishes/Reusing_references/Research) shows that reuse, variation, and maintenance add another layer of difficulty.
- Similar friction appears outside Wikimedia too: [Obstacles to Dataset Citation Using Bibliographic Management Software](https://datascience.codata.org/articles/10.5334/dsj-2025-017) found that major reference managers often fail to import or export complete citation metadata accurately.

### Why It's Complex

At citation time, editors often have to resolve too many things at once:

- what source they are citing
- how that source should be named
- which edition, version, or format matters
- what locator points to the relevant material
- how a reader can access the source
- whether an existing record should be reused or a new one created

Many citation systems force contributors to answer them all in one moment, while they are also trying to finish an edit.
