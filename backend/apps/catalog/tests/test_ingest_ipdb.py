"""Integration tests for the ingest_ipdb command."""

import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.catalog.ingestion.ipdb.features import extract_ipdb_gameplay_features
from apps.catalog.models import (
    Credit,
    MachineModel,
    Manufacturer,
    Person,
    System,
    SystemMpuString,
)
from apps.catalog.tests.conftest import make_machine_model
from apps.provenance.models import Source

FIXTURES = "apps/catalog/tests/fixtures"


@pytest.fixture
def _mpu_strings(db):
    """Create SystemMpuString records matching the fixture's system.json."""
    mfr, _ = Manufacturer.objects.get_or_create(
        slug="williams", defaults={"name": "Williams"}
    )
    system = System.objects.create(slug="wpc-95", name="WPC-95", manufacturer=mfr)
    SystemMpuString.objects.create(system=system, value="Williams WPC-95")


@pytest.fixture
def _ipdb_sample_models(db):
    """Pre-seed MachineModels that ingest_ipdb expects to exist in pindata.

    Pindata is the authoritative superset of machines, so IPDB ingest
    matches by ipdb_id rather than creating. Mirror that with pre-seeded
    rows covering every record in ipdb_sample.json.
    """
    make_machine_model(name="Medieval Madness", slug="medieval-madness", ipdb_id=4000)
    make_machine_model(name="A-B-C Bowler", slug="a-b-c-bowler", ipdb_id=20)
    make_machine_model(name="The Addams Family", slug="the-addams-family", ipdb_id=61)
    make_machine_model(name="Baffle Ball", slug="baffle-ball", ipdb_id=100)


@pytest.fixture
def _run_ipdb(
    db,
    credit_roles,
    _mpu_strings,
    ingest_taxonomy,
    ipdb_locations,
    ipdb_narrative_features,
    _ipdb_sample_models,
):
    """Run ingest_ipdb with the sample fixture."""
    call_command(
        "ingest_ipdb",
        ipdb=f"{FIXTURES}/ipdb_sample.json",
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("_run_ipdb")
class TestIngestIpdb:
    """Integration tests against a pre-seeded MachineModel set.

    IPDB ingest no longer creates MachineModels — pindata is the authoritative
    superset, so every IPDB record must match a pre-seeded MM (see the
    ``_ipdb_sample_models`` fixture). These tests verify reconciliation,
    claim assertion, and downstream entity creation (Persons, Credits, etc.).
    """

    def test_creates_source(self):
        source = Source.objects.get(slug="ipdb")
        assert source.name == "IPDB"
        assert source.priority == 100

    def test_all_records_reconciled_no_extras_created(self):
        """Every pre-seeded MM is matched; ingest adds no MMs and removes none."""
        assert MachineModel.objects.count() == 4
        assert MachineModel.objects.filter(ipdb_id=4000).exists()
        assert MachineModel.objects.filter(ipdb_id=20).exists()
        assert MachineModel.objects.filter(ipdb_id=61).exists()
        assert MachineModel.objects.filter(ipdb_id=100).exists()

    def test_claims_created(self):
        pm = MachineModel.objects.get(ipdb_id=4000)
        source = Source.objects.get(slug="ipdb")
        active_claims = pm.claims.filter(source=source, is_active=True)

        # IPDB does not assert name claims — pindata is the authoritative
        # name source (IPDB titles often contain encoding corruption).
        claim_fields = set(active_claims.values_list("field_name", flat=True))
        assert "year" in claim_fields
        assert "technology_generation" in claim_fields
        assert "ipdb_rating" in claim_fields

    def test_date_parsing(self):
        pm = MachineModel.objects.get(ipdb_id=4000)
        source = Source.objects.get(slug="ipdb")
        year_claim = pm.claims.get(source=source, field_name="year", is_active=True)
        assert year_claim.value == 1997
        month_claim = pm.claims.get(source=source, field_name="month", is_active=True)
        assert month_claim.value == 6

    def test_year_only_date(self):
        pm = MachineModel.objects.get(ipdb_id=20)
        source = Source.objects.get(slug="ipdb")
        year_claim = pm.claims.get(source=source, field_name="year", is_active=True)
        assert year_claim.value == 1941
        assert not pm.claims.filter(
            source=source, field_name="month", is_active=True
        ).exists()

    def test_credits_created(self):
        pm = MachineModel.objects.get(ipdb_id=4000)
        credits = Credit.objects.filter(model=pm)
        assert credits.count() == 4
        assert credits.filter(role__slug="design", person__name="Brian Eddy").exists()
        assert credits.filter(role__slug="art", person__name="John Youssi").exists()
        assert credits.filter(
            role__slug="software", person__name="Lyman Sheats"
        ).exists()

    def test_multi_credit_string(self):
        pm = MachineModel.objects.get(ipdb_id=61)
        design_credits = Credit.objects.filter(model=pm, role__slug="design")
        assert design_credits.count() == 2
        names = set(design_credits.values_list("person__name", flat=True))
        assert names == {"Pat Lawlor", "Larry DeMar"}

    def test_persons_created(self):
        assert Person.objects.count() == 6

    def test_pure_mechanical_type(self):
        pm = MachineModel.objects.get(ipdb_id=100)
        source = Source.objects.get(slug="ipdb")
        type_claim = pm.claims.get(
            source=source, field_name="technology_generation", is_active=True
        )
        assert type_claim.value == "pure-mechanical"

    def test_idempotent(self):
        call_command(
            "ingest_ipdb",
            ipdb=f"{FIXTURES}/ipdb_sample.json",
        )
        assert MachineModel.objects.count() == 4
        assert Person.objects.count() == 6

    def test_system_claim_created(self):
        """Medieval Madness has MPU 'Williams WPC-95' → system claim value 'wpc-95'."""
        pm = MachineModel.objects.get(ipdb_id=4000)
        source = Source.objects.get(slug="ipdb")
        claim = pm.claims.filter(
            source=source, field_name="system", is_active=True
        ).first()
        assert claim is not None
        assert claim.value == "wpc-95"

    def test_no_mpu_no_system_claim(self):
        """Records without MPU do not produce a system claim."""
        pm = MachineModel.objects.get(ipdb_id=20)
        source = Source.objects.get(slug="ipdb")
        assert not pm.claims.filter(
            source=source, field_name="system", is_active=True
        ).exists()


@pytest.mark.django_db
class TestIngestIpdbDryRun:
    def test_dry_run_creates_nothing(
        self,
        db,
        credit_roles,
        _mpu_strings,
        ingest_taxonomy,
        ipdb_locations,
        ipdb_narrative_features,
        _ipdb_sample_models,
    ):
        """--dry-run validates the plan without writing entities or claims."""
        initial_mm = MachineModel.objects.count()
        initial_persons = Person.objects.count()

        call_command(
            "ingest_ipdb",
            ipdb=f"{FIXTURES}/ipdb_sample.json",
            dry_run=True,
        )

        assert MachineModel.objects.count() == initial_mm
        assert Person.objects.count() == initial_persons
        assert Source.objects.filter(slug="ipdb").exists() is not False
        # Source IS created (get_or_create_source runs before plan), but
        # no IngestRun should exist (dry-run skips it).
        from apps.provenance.models import IngestRun

        assert IngestRun.objects.count() == 0

    def test_dry_run_then_real_run(
        self,
        db,
        credit_roles,
        _mpu_strings,
        ingest_taxonomy,
        ipdb_locations,
        ipdb_narrative_features,
        _ipdb_sample_models,
    ):
        """Dry-run is a no-op; the real run then populates Person rows."""
        initial_mm = MachineModel.objects.count()
        call_command(
            "ingest_ipdb",
            ipdb=f"{FIXTURES}/ipdb_sample.json",
            dry_run=True,
        )
        assert MachineModel.objects.count() == initial_mm
        assert Person.objects.count() == 0

        call_command(
            "ingest_ipdb",
            ipdb=f"{FIXTURES}/ipdb_sample.json",
        )
        # IPDB no longer creates MachineModels — they must pre-exist.
        assert MachineModel.objects.count() == initial_mm
        assert Person.objects.count() == 6


@pytest.mark.django_db
@pytest.mark.django_db
class TestIngestIpdbUnknownMpu:
    @pytest.mark.usefixtures("ipdb_narrative_features", "credit_roles")
    def test_unknown_mpu_raises_command_error(self, db, tmp_path):
        make_machine_model(name="Mystery Machine", slug="mystery-machine", ipdb_id=9999)
        fixture = tmp_path / "bad_ipdb.json"
        fixture.write_text(
            json.dumps(
                {
                    "Data": [
                        {
                            "IpdbId": 9999,
                            "Title": "Mystery Machine",
                            "ManufacturerId": 999,
                            "Type": "Solid State (SS)",
                            "TypeShortName": "SS",
                            "MPU": "Unknown Board X-99",
                        }
                    ]
                }
            )
        )
        # No SystemMpuString records exist, so the MPU is unknown.
        with pytest.raises(CommandError, match="Unknown MPU strings"):
            call_command(
                "ingest_ipdb",
                ipdb=str(fixture),
            )


# ---------------------------------------------------------------------------
# Unit tests for extract_ipdb_gameplay_features
#
# All test inputs are complete, unmodified NotableFeatures strings taken
# directly from the IPDB dataset (via pinexplore DuckDB explore.duckdb).
# Expected slug sets are derived from the ipdb_gameplay_features SQL view
# (sql/03_staging.sql) plus the _NARRATIVE_FEATURE_PATTERNS pass.
# IpdbIds are noted for traceability.
# ---------------------------------------------------------------------------

# Feature map drawn from the actual pinbase gameplay_feature vocabulary
# (ref_feature_gameplay view in pinexplore).  Includes every term needed
# by the test cases below.
_FM = {
    "3-bank standup targets": "3-bank-standup-targets",
    "4-bank drop targets": "4-bank-drop-targets",
    "5-bank drop targets": "5-bank-drop-targets",
    "captive ball": "captive-ball",
    "captive balls": "captive-ball",
    "drop targets": "drop-targets",
    "electromagnets": "magnets",
    "flippers": "flippers",
    "gobble hole": "gobble-holes",
    "gobble holes": "gobble-holes",
    "horseshoe diverter": "horseshoe-diverters",
    "multiball": "multiball",
    "2-ball multiball": "2-ball-multiball",
    "3-ball multiball": "3-ball-multiball",
    "4-ball multiball": "4-ball-multiball",
    "6-ball multiball": "6-ball-multiball",
    "kick-out hole": "kick-out-holes",
    "kick-out holes": "kick-out-holes",
    "newton ball": "newton-balls",
    "passive bumpers": "passive-bumpers",
    "pop bumpers": "pop-bumpers",
    "rollunder": "rollunders",
    "roto-targets": "roto-targets",
    "scoring bumpers": "scoring-bumpers",
    "slingshots": "slingshots",
    "spinning target": "spinning-targets",
    "spinning targets": "spinning-targets",
    "spring bumpers": "spring-bumpers",
    "standup targes": "standup-targets",  # real IPDB typo, resolved via alias
    "standup targets": "standup-targets",
    "trap holes": "trap-holes",
    "vertical up-kicker": "vertical-up-kickers",
    "whirlpool": "whirlpools",
}


class TestExtractIpdbGameplayFeatures:
    """Unit tests for the extract_ipdb_gameplay_features parsing pipeline.

    Every raw string is a complete, verbatim IPDB NotableFeatures value.

    DISCIPLINE: whenever ingest_ipdb fails or produces wrong output while
    parsing a NotableFeatures string, add that *complete* string as a new
    test case here before fixing the code.  Use the IpdbId in the test name
    for traceability back to the source record in pinexplore.
    """

    def _slugs(self, raw: str) -> set[str]:
        pairs, _ = extract_ipdb_gameplay_features(raw, _FM)
        return {slug for slug, _count in pairs}

    def _counts(self, raw: str) -> dict[str, int | None]:
        pairs, _ = extract_ipdb_gameplay_features(raw, _FM)
        return dict(pairs)

    def _unmatched(self, raw: str) -> list[str]:
        _, unmatched = extract_ipdb_gameplay_features(raw, _FM)
        return unmatched

    def test_ipdb_876_two_features(self):
        # IpdbId 876: minimal two-feature string
        raw = "Passive bumpers (12), Kick-out hole (1)."
        assert self._slugs(raw) == {"passive-bumpers", "kick-out-holes"}

    def test_ipdb_2079_scoring_bumpers(self):
        # IpdbId 2079
        raw = "Scoring bumpers (14), Kick-out hole (1)."
        assert self._slugs(raw) == {"scoring-bumpers", "kick-out-holes"}

    def test_ipdb_2333_trailing_narrative(self):
        # IpdbId 2333: single feature + trailing prose after period
        raw = "Trap holes (36). Advertised as having a 30-inch backboard."
        assert self._slugs(raw) == {"trap-holes"}

    def test_ipdb_2805_gobble_hole(self):
        # IpdbId 2805: mixed feature types, trailing note
        raw = "Flippers (2), Pop bumpers (3), Kick-out hole (1), Gobble hole (1). 5 balls for 5 cents."
        assert self._slugs(raw) == {
            "flippers",
            "pop-bumpers",
            "kick-out-holes",
            "gobble-holes",
        }

    def test_ipdb_3117_period_uppercase_artifact(self):
        # IpdbId 3117: "B.C." triggers the period+uppercase comma-insertion rule;
        # must not corrupt feature extraction.
        raw = "Spring bumpers (8), Kick-out holes (3). Playfield has a ball-advance operation similar to the Tar Pit in Bally's 1971 'Four Million B.C.'. Reclined backbox."
        assert self._slugs(raw) == {"spring-bumpers", "kick-out-holes"}

    def test_ipdb_3147_dimension_paren_skipped(self):
        # IpdbId 3147: "(42 inches long including coin slide)" must NOT match
        # the count pattern — only bare (N) integers qualify.
        raw = "10 balls for 5 cents. Trap holes (14). Games measures 39 inches long (42 inches long including coin slide), 24 inches wide, and 52 inches high in the back."
        assert self._slugs(raw) == {"trap-holes"}

    def test_ipdb_302_horseshoe_diverter(self):
        # IpdbId 302: feature buried after narrative preamble; long trailing text
        raw = '10 balls for 5 cents. Horseshoe diverter (1). Walnut playfield. Cabinet advertised as 39 inches long, 16 inches wide, with "lustrous Ebony Black and Silver Striping".'
        assert self._slugs(raw) == {"horseshoe-diverters"}

    def test_ipdb_4920_clean_list(self):
        # IpdbId 4920: clean comma-delimited list
        raw = "Flippers (2), Pop bumpers (2), Kick-out holes (5), Drop targets (20)."
        assert self._slugs(raw) == {
            "flippers",
            "pop-bumpers",
            "kick-out-holes",
            "drop-targets",
        }

    def test_ipdb_4431_mixed_bank_targets_and_rollunder(self):
        # IpdbId 4431: uppercase "Bank" in feature name lowercased correctly;
        # "Mini-playfield at upper left" triggers the \bMini.?playfield\b
        # narrative pattern → multi-level-playfield added.
        raw = "Flippers (4), Slingshots (2), Spinning targets (2), 5-Bank drop targets (1), 4-Bank drop targets (1), Rollunder (1). Mini-playfield at upper left. No pop bumpers."
        assert self._slugs(raw) == {
            "flippers",
            "slingshots",
            "spinning-targets",
            "5-bank-drop-targets",
            "4-bank-drop-targets",
            "rollunders",
            "multi-level-playfield",
        }

    def test_ipdb_5304_standup_typo_alias(self):
        # IpdbId 5304: "Standup targes" is a real IPDB typo, resolved via alias
        raw = "Flippers (4), Pop bumpers (3), Standup targes (3), Roto-targets (2), Kicker between flipper propels ball upward to center target. Wedge head."
        assert self._slugs(raw) == {
            "flippers",
            "pop-bumpers",
            "standup-targets",
            "roto-targets",
        }

    def test_ipdb_5486_multiline_ignored(self):
        # IpdbId 5486: features before first period extracted; multi-paragraph
        # content after is irrelevant and must not cause errors.
        raw = "Flippers (2), Pop bumpers (3), Slingshots (2), Standup targets (8). Wedge head. Drop-down cabinet.\r\n\r\nMaximum displayed point score is 9,999 points.\r\n\r\nSound: EM chimes"
        assert self._slugs(raw) == {
            "flippers",
            "pop-bumpers",
            "slingshots",
            "standup-targets",
        }

    def test_ipdb_5704_multi_bank_drop_targets(self):
        # IpdbId 5704: both bank sizes, trailing note
        raw = "Flippers (8), Pop bumpers (4), 5-bank drop targets (1), 4-bank drop targets (1). Three Level Playfield."
        assert self._slugs(raw) == {
            "flippers",
            "pop-bumpers",
            "5-bank-drop-targets",
            "4-bank-drop-targets",
        }

    def test_ipdb_1853_compound_paren_skipped(self):
        # IpdbId 1853: "(5-ball mode and add-a-ball-mode)" and "(extended play mode)"
        # must not match — only bare (N) integers qualify.
        raw = "Flippers (2), Pop bumpers (5), Slingshots (4), Standup targets (7). A flipper-like gate under the apron routes the ball either to the outhole for delivery to the shooter lane (5-ball mode and add-a-ball-mode) or to a kicker which propels the ball upwards through the flippers and back into play (extended play mode).\r\n\r\nSound: bell, wooden box chime."
        assert self._slugs(raw) == {
            "flippers",
            "pop-bumpers",
            "slingshots",
            "standup-targets",
        }

    def test_ipdb_6098_notable_features_prefix(self):
        # IpdbId 6098: "Notable Features:" prefix stripped before parsing
        raw = "Notable Features: Flippers (2), Pop bumpers (4), Slingshots (2), Standup targets (7), 5-bank drop targets (1), Spinning target (1), Captive ball (1), Whirlpool (1).\r\n\r\nNumber of pinballs installed: 6\r\n\r\nAdvertised as all LED general illumination and control lamps. A translite is used instead of a backglass.\r\n\r\nThe manufacturer provided the wiring for a shaker motor but did not provide the motor itself. Customers had to buy the shaker motor from after-factory providers."
        assert self._slugs(raw) == {
            "flippers",
            "pop-bumpers",
            "slingshots",
            "standup-targets",
            "5-bank-drop-targets",
            "spinning-targets",
            "captive-ball",
            "whirlpools",
        }

    def test_ipdb_6332_notable_features_prefix_long_list(self):
        # IpdbId 6332: "Notable Features:" prefix + long structured list +
        # multi-paragraph prose with mojibake (U+FFFD → space).
        # "Up-post in upper playfield" fires the \bUpper playfield\b narrative
        # pattern → multi-level-playfield added.
        raw = 'Notable Features: Flippers (2), Pop bumpers (3), Slingshots (2), Standup targets (9), Captive balls (6), Drop targets (2), Kick-out holes (2), Vertical up-kicker (1), Spinning target (1), Newton ball (1), Up-post in upper playfield, Dual inlanes, Bi-directional ramp, Stereo sound, Speech.\r\n\r\nBlack powder-coated legs, armor, hinges, front molding. Backbox has powder-coated steel and plywood. A "Ghostbusters and Terror Dogs" translite is used instead of a backglass. Decal cabinet artwork. Traditional playfield rod supports.\r\n\r\nBall composition: 1-1/6 inch steel\r\n\r\nFactory-installed illumination:\r\nPop bumpers have LED lighting. 7 full spectrum color-changing RGB LED\ufffd\'s under playfield arrow inserts. All LED general illumination.'
        assert self._slugs(raw) == {
            "flippers",
            "pop-bumpers",
            "slingshots",
            "standup-targets",
            "captive-ball",
            "drop-targets",
            "kick-out-holes",
            "vertical-up-kickers",
            "spinning-targets",
            "newton-balls",
            "multi-level-playfield",
        }

    def test_ipdb_6333_notable_features_electromagnets(self):
        # IpdbId 6333: "Electromagnets (2)" resolves via alias to "magnets";
        # mojibake U+FFFD in trailing prose must not corrupt parsing.
        # "Up-post in upper playfield" fires the \bUpper playfield\b narrative
        # pattern → multi-level-playfield added.
        raw = 'Notable Features: Flippers (2), Pop bumpers (3), Standup targets (9), Captive balls (6), Drop targets (2), Kick-out holes (2), Electromagnets (2), Vertical up-kicker (1), Spinning target (1), Newton ball (1), Up-post in upper playfield, Dual inlanes, Stereo sound, Speech. Interactive holograph projector. Two electromagnets under the lower playfield simulate slingshot action.\r\n\r\nBlack powder-coated legs, armor, hinges, front molding. Backbox has powder-coated steel and plywood. Powder-coated steel bottom arch. A "Ghostbusters and Stay Puft" translite is used instead of a backglass. Decal cabinet artwork. Playfield side support and brackets.\r\n \r\nBall composition: 1-1/6 inch steel\r\n\r\nFactory-installed illumination:\r\nPop bumpers have LED lighting. 7 full spectrum color-changing RGB LED\ufffd\'s under playfield arrow inserts. All LED general illumination.'
        assert self._slugs(raw) == {
            "flippers",
            "pop-bumpers",
            "standup-targets",
            "captive-ball",
            "drop-targets",
            "kick-out-holes",
            "magnets",
            "vertical-up-kickers",
            "spinning-targets",
            "newton-balls",
            "multi-level-playfield",
        }

    def test_ipdb_6448_mechanical_animation_paren_skipped(self):
        # IpdbId 6448: "(hula dancer)" has no digits — must not match count pattern
        raw = "Flippers (2), Pop bumpers (5), Slingshots (2), Standup targets (5), Kick-out hole (1). Mechanical backbox animation (hula dancer). Red insert between flippers for kick-up when lit."
        assert self._slugs(raw) == {
            "flippers",
            "pop-bumpers",
            "slingshots",
            "standup-targets",
            "kick-out-holes",
        }

    def test_ipdb_106_multiball_via_narrative_pattern(self):
        # IpdbId 106: structured features extracted by count pipeline;
        # "3-ball Multiball" in the narrative fires the \bMulti-?ball\b pattern.
        # Note: "4-bank drop targets" has no count in this entry → not extracted.
        raw = 'Flippers (2), Pop bumpers (3), Mechanically raised/lowered ramp, Loop Shot, 4-bank drop targets, 3-bank standup targets (3), Spinning target (1), Vertical up-kicker (1), Center up-post, 3-ball Multiball. Submarine on the upper left playfield saves 3 "divers" (balls locked) then kicks them onto playfield at the start of multiball.'
        assert self._slugs(raw) == {
            "flippers",
            "pop-bumpers",
            "3-bank-standup-targets",
            "spinning-targets",
            "vertical-up-kickers",
            "3-ball-multiball",
        }

    def test_ipdb_195_multiball_3_count(self):
        # IpdbId 195: "Multiball (3)" → 3-ball-multiball via count pipeline
        raw = "Flippers (2), Multiball (3)"
        assert self._slugs(raw) == {"flippers", "3-ball-multiball"}

    def test_ipdb_528_multiball_2_count(self):
        # IpdbId 528: "Multiball (2)" → 2-ball-multiball via count pipeline
        raw = "Multiball (2)"
        assert self._slugs(raw) == {"2-ball-multiball"}

    def test_ipdb_778_multiball_paren_2_ball(self):
        # IpdbId 778: "Multiball (2-ball)" — hyphenated variant in parens
        raw = "Flippers (6), Kick-out holes (2), Rollunder spinners (2). Multiball (2-ball), Captive ball (1), 2-in-line drop targets, Three-level playfield, Speech, Plexiglas main playfield covering. No pop bumpers on this game."
        assert "2-ball-multiball" in self._slugs(raw)
        assert "multiball" not in self._slugs(raw)

    def test_ipdb_5767_multiball_paren_multiple(self):
        # IpdbId 5767: "Multiball (2-Ball, 3-Ball, 4-Ball)" — multiple variants
        raw = "Flippers (2), Pop bumpers (3), Slingshots (2), Standup targets (15), Spinning target (1), Rotating ball cannon, Multiball (2-Ball, 3-Ball, 4-Ball). Cabinet advertised as 55 inches long, 27 inches wide, and 75 1/2 inches high; 250 lbs."
        slugs = self._slugs(raw)
        assert {"2-ball-multiball", "3-ball-multiball", "4-ball-multiball"} <= slugs
        assert "multiball" not in slugs

    def test_ipdb_3072_multiball_paren_modes_not_balls(self):
        # IpdbId 3072: "Multiball (3 Modes)" — 3 is mode count, NOT ball count
        raw = "Flippers (2), Ramps (2), Multiball (3 Modes), Autoplunger."
        assert "multiball" in self._slugs(raw)
        assert "3-ball-multiball" not in self._slugs(raw)

    def test_ipdb_4664_multiball_paren_ball_and_modes(self):
        # IpdbId 4664: "Multiball (4 ball, 3 modes)" — 4 is balls, 3 is modes
        raw = "Flippers (2), Pop bumpers (4), 4-bank drop targets (2), Multiball (4 ball, 3 modes), Up-post between flippers, Shaker motor."
        slugs = self._slugs(raw)
        assert "4-ball-multiball" in slugs
        assert "3-ball-multiball" not in slugs

    def test_ipdb_49_multiball_2_narrative(self):
        # IpdbId 49: "2-ball multiball" in narrative text
        raw = "Flippers (2), Pop bumpers (3), Slingshots (2), Standup targets (6), Kick-out hole (1), Spinning target (1), Rollunder (1), 2-ball multiball. Has speech.\r\n\r\nActual measured weight: 225 lbs (includes legs)."
        assert self._slugs(raw) == {
            "flippers",
            "pop-bumpers",
            "slingshots",
            "standup-targets",
            "kick-out-holes",
            "spinning-targets",
            "rollunders",
            "2-ball-multiball",
        }

    def test_ipdb_610_multiball_compound_narrative(self):
        # IpdbId 610: "2-ball and 3-ball Multiball" — compound narrative phrase
        raw = "Flippers (2), Slingshots (4), 7-bank drop targets (2), Standup targets (21), Kick-out holes (3), Captive balls (2), Kick-target (1), 2-ball and 3-ball Multiball."
        slugs = self._slugs(raw)
        assert {"2-ball-multiball", "3-ball-multiball"} <= slugs
        assert "multiball" not in slugs

    def test_ipdb_82_three_ball_multiball_spelled_out(self):
        # IpdbId 82: "Three ball multiball" — spelled-out number
        raw = "Flippers (2), 4-bank drop targets (1). Three ball multiball. Right outlane detour gate (between outlane and inlane). Shooter lane detour gate (between shooter lane and outlane). No pop bumpers on this game."
        assert "3-ball-multiball" in self._slugs(raw)
        assert "multiball" not in self._slugs(raw)

    def test_multiball_unknown_count_falls_back_to_generic(self):
        # 5-ball-multiball not in vocabulary → falls back to generic "multiball"
        raw = "Flippers (2), Multiball (5)."
        assert self._slugs(raw) == {"flippers", "multiball"}

    def test_unmatched_terms_returned(self):
        # IpdbId 302: "horseshoe diverter" is in _FM; the narrative preamble
        # ("10 balls for 5 cents") and cabinet note produce no segments with
        # bare (N), so the only unmatched term should be none — diverter matches.
        raw = '10 balls for 5 cents. Horseshoe diverter (1). Walnut playfield. Cabinet advertised as 39 inches long, 16 inches wide, with "lustrous Ebony Black and Silver Striping".'
        assert self._unmatched(raw) == []

    def test_deduplication(self):
        # Singular and plural forms of the same feature resolve to the same slug;
        # must appear only once in the output list.
        # IpdbId 876-style: "Kick-out hole" and a hypothetical plural back-to-back.
        raw = "Passive bumpers (12), Kick-out hole (1), Kick-out holes (1)."
        pairs, _ = extract_ipdb_gameplay_features(raw, _FM)
        slug_list = [slug for slug, _count in pairs]
        assert slug_list.count("kick-out-holes") == 1

    # --- Count extraction tests ---

    def test_count_single_feature(self):
        # "Flippers (2)" → flippers with count 2
        raw = "Flippers (2)."
        assert self._counts(raw) == {"flippers": 2}

    def test_count_multiple_features(self):
        # Full string with multiple counts
        raw = "Flippers (2), Pop bumpers (3), Slingshots (2), Standup targets (8)."
        counts = self._counts(raw)
        assert counts["flippers"] == 2
        assert counts["pop-bumpers"] == 3
        assert counts["slingshots"] == 2
        assert counts["standup-targets"] == 8

    def test_count_multiball_not_stored(self):
        # "Multiball (3)" → 3-ball-multiball slug with NO count
        # The parenthesized number is a qualifier, not a quantity.
        raw = "Flippers (2), Multiball (3)"
        counts = self._counts(raw)
        assert counts["flippers"] == 2
        assert counts["3-ball-multiball"] is None

    def test_count_multiball_paren_complex_not_stored(self):
        # "Multiball (2-Ball, 3-Ball)" → slug variants with no count
        raw = "Multiball (2-Ball, 3-Ball, 4-Ball)"
        counts = self._counts(raw)
        assert counts["2-ball-multiball"] is None
        assert counts["3-ball-multiball"] is None
        assert counts["4-ball-multiball"] is None

    def test_count_narrative_no_count(self):
        # Narrative-only features have no count
        raw = "3-ball Multiball. Ball Save."
        counts = self._counts(raw)
        assert counts["3-ball-multiball"] is None
        assert counts["ball-save"] is None

    def test_count_mixed_counted_and_narrative(self):
        # IpdbId 106-style: structured features with counts + narrative multiball
        raw = "Flippers (2), Pop bumpers (3), Spinning target (1), 3-ball Multiball."
        counts = self._counts(raw)
        assert counts["flippers"] == 2
        assert counts["pop-bumpers"] == 3
        assert counts["spinning-targets"] == 1
        assert counts["3-ball-multiball"] is None
