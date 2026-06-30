#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "astro_calc.h"

static int passed = 0, failed = 0;

#define FAIL_UNLESS(cond, fmt, ...) do { \
    if (cond) { passed++; } else { \
        failed++; \
        printf("FAIL: " fmt "\n", ##__VA_ARGS__); \
    } \
} while(0)

static void test_orb_thresholds(void) {
    printf("\n--- Orb Threshold Tests ---\n");
    ac_aspect_t asp;

    /* 91 deg vs Square (90): 1 deg orb should NOT detect with Tight (1).
     * It SHOULD detect with Modern (6) or Classical (4). */
    ac_detect_aspect(0.0, 0.0, 91.0, 0.0, AC_ORB_TIGHT, &asp);
    FAIL_UNLESS(asp.aspect == AC_ASP_NONE,
                "91° with Tight preset should NOT be square (orb 1°)");

    ac_detect_aspect(0.0, 0.0, 91.0, 0.0, AC_ORB_MODERN, &asp);
    FAIL_UNLESS(asp.aspect == AC_ASP_SQUARE,
                "91° with Modern preset SHOULD be square (orb 1° <= 6°)");

    ac_detect_aspect(0.0, 0.0, 91.0, 0.0, AC_ORB_CLASSICAL, &asp);
    FAIL_UNLESS(asp.aspect == AC_ASP_SQUARE,
                "91° with Classical preset SHOULD be square (orb 1° <= 4°)");

    /* 89.5 deg vs Square (90): orb 0.5 — should detect with Tight */
    ac_detect_aspect(0.0, 0.0, 89.5, 0.0, AC_ORB_TIGHT, &asp);
    FAIL_UNLESS(asp.aspect == AC_ASP_SQUARE,
                "89.5° with Tight preset SHOULD be square (orb 0.5° <= 1°)");

    /* 150.5 deg vs Quincunx (150): orb 0.5 — should detect with Modern (2) */
    ac_detect_aspect(0.0, 0.0, 150.5, 0.0, AC_ORB_MODERN, &asp);
    FAIL_UNLESS(asp.aspect == AC_ASP_QUINCUNX,
                "150.5° with Modern SHOULD be quincunx (orb 0.5°)");

    /* 152 deg vs Quincunx (150): orb 2 — should NOT detect with Modern (2),
     * but SHOULD with Wide (3) */
    ac_detect_aspect(0.0, 0.0, 152.0, 0.0, AC_ORB_MODERN, &asp);
    FAIL_UNLESS(asp.aspect == AC_ASP_NONE,
                "152° with Modern should NOT be quincunx (orb exactly 2°)");

    ac_detect_aspect(0.0, 0.0, 152.0, 0.0, AC_ORB_WIDE, &asp);
    FAIL_UNLESS(asp.aspect == AC_ASP_QUINCUNX,
                "152° with Wide SHOULD be quincunx (orb 2° <= 3°)");

    /* Conjunction at 0 deg exact */
    ac_detect_aspect(120.0, 0.0, 120.0, 0.0, AC_ORB_TIGHT, &asp);
    FAIL_UNLESS(asp.aspect == AC_ASP_CONJUNCTION,
                "Exact conjunction should detect with Tight");
    FAIL_UNLESS(fabs(asp.orb) < 1e-9,
                "Exact conjunction orb should be ~0, got %.6f", asp.orb);
}

static void test_known_chart(void) {
    printf("\n--- Known Chart Aspects (Xephyr) ---\n");
    if (ac_init(NULL) != AC_OK) {
        printf("FAIL: init\n");
        failed++;
        return;
    }
    double jd = ac_date_to_jd(1969, 11, 30, 20, 43, 0, -6.0);
    int ids[] = {
        AC_SUN, AC_MOON, AC_MERCURY, AC_VENUS, AC_MARS,
        AC_JUPITER, AC_SATURN, AC_URANUS, AC_NEPTUNE, AC_PLUTO
    };
    int n = sizeof(ids)/sizeof(ids[0]);
    ac_body_t b[10];
    ac_calc_bodies(jd, ids, n, b);

    printf("%-12s <-> %-12s %2s %-14s %6s %6s %4s\n",
           "Body1", "Body2", "Pr", "Aspect", "Angle", "Orb", "App");
    printf("%s\n", "--------------------------------------------------------------");

    int found_sun_uranus_sextile_modern = 0;
    int found_moon_venus_square_modern = 0;
    int found_moon_jupiter_sextile_modern = 0;
    int found_moon_saturn_trine_modern = 0;
    int found_mercury_mars_sextile_modern = 0;
    int found_venus_neptune_conj_modern = 0;
    int found_jupiter_saturn_oppo_modern = 0;
    int found_jupiter_neptune_semisextile_modern = 0;
    int found_neptune_pluto_sextile_modern = 0;
    int found_moon_pluto_semisextile_modern = 0;

    for (int i = 0; i < n; i++) {
        for (int j = i + 1; j < n; j++) {
            ac_aspect_t a;
            ac_detect_aspect(b[i].longitude, b[i].speed,
                             b[j].longitude, b[j].speed,
                             AC_ORB_MODERN, &a);
            if (a.aspect != AC_ASP_NONE) {
                printf("%-12s <-> %-12s %2s %-14s %6.2f %6.2f %4s\n",
                       b[i].name, b[j].name,
                       "M", a.aspect_name, a.actual_angle, a.orb,
                       a.applying ? "App" : "Sep");
            }
            ac_detect_aspect(b[i].longitude, b[i].speed,
                             b[j].longitude, b[j].speed,
                             AC_ORB_TIGHT, &a);
            if (a.aspect != AC_ASP_NONE) {
                printf("%-12s <-> %-12s %2s %-14s %6.2f %6.2f %4s\n",
                       b[i].name, b[j].name,
                       "T", a.aspect_name, a.actual_angle, a.orb,
                       a.applying ? "App" : "Sep");
            }

            ac_detect_aspect(b[i].longitude, b[i].speed,
                             b[j].longitude, b[j].speed,
                             AC_ORB_MODERN, &a);
            if (a.aspect == AC_ASP_SEXTILE && b[i].body_id == AC_SUN && b[j].body_id == AC_URANUS)
                found_sun_uranus_sextile_modern = 1;
            if (a.aspect == AC_ASP_SQUARE && b[i].body_id == AC_MOON && b[j].body_id == AC_VENUS)
                found_moon_venus_square_modern = 1;
            if (a.aspect == AC_ASP_SEXTILE && b[i].body_id == AC_MOON && b[j].body_id == AC_JUPITER)
                found_moon_jupiter_sextile_modern = 1;
            if (a.aspect == AC_ASP_TRINE && b[i].body_id == AC_MOON && b[j].body_id == AC_SATURN)
                found_moon_saturn_trine_modern = 1;
            if (a.aspect == AC_ASP_SEXTILE && b[i].body_id == AC_MERCURY && b[j].body_id == AC_MARS)
                found_mercury_mars_sextile_modern = 1;
            if (a.aspect == AC_ASP_CONJUNCTION && b[i].body_id == AC_VENUS && b[j].body_id == AC_NEPTUNE)
                found_venus_neptune_conj_modern = 1;
            if (a.aspect == AC_ASP_OPPOSITION && b[i].body_id == AC_JUPITER && b[j].body_id == AC_SATURN)
                found_jupiter_saturn_oppo_modern = 1;
            if (a.aspect == AC_ASP_SEMISEXTILE && b[i].body_id == AC_JUPITER && b[j].body_id == AC_NEPTUNE)
                found_jupiter_neptune_semisextile_modern = 1;
            if (a.aspect == AC_ASP_SEXTILE && b[i].body_id == AC_NEPTUNE && b[j].body_id == AC_PLUTO)
                found_neptune_pluto_sextile_modern = 1;
            if (a.aspect == AC_ASP_SEMISEXTILE && b[i].body_id == AC_MOON && b[j].body_id == AC_PLUTO)
                found_moon_pluto_semisextile_modern = 1;
        }
    }

    ac_cleanup();

    FAIL_UNLESS(found_sun_uranus_sextile_modern,
                "Sun-Uranus sextile not detected (expected ~60.8°)");
    FAIL_UNLESS(found_moon_venus_square_modern,
                "Moon-Venus square not detected (expected ~88.3°)");
    FAIL_UNLESS(found_moon_jupiter_sextile_modern,
                "Moon-Jupiter sextile not detected (expected ~60.0°)");
    FAIL_UNLESS(found_moon_saturn_trine_modern,
                "Moon-Saturn trine not detected (expected ~114.2°)");
    FAIL_UNLESS(found_mercury_mars_sextile_modern,
                "Mercury-Mars sextile not detected (expected ~62.3°)");
    FAIL_UNLESS(found_venus_neptune_conj_modern,
                "Venus-Neptune conjunction not detected (expected ~3.2°)");
    FAIL_UNLESS(found_jupiter_saturn_oppo_modern,
                "Jupiter-Saturn opposition not detected (expected ~174.2°)");
    FAIL_UNLESS(found_jupiter_neptune_semisextile_modern,
                "Jupiter-Neptune semisextile not detected (expected ~31.6°)");
    FAIL_UNLESS(found_neptune_pluto_sextile_modern,
                "Neptune-Pluto sextile not detected (expected ~61.7°)");
    FAIL_UNLESS(found_moon_pluto_semisextile_modern,
                "Moon-Pluto semisextile not detected (expected ~29.9°)");
}

static void test_applying_separating(void) {
    printf("\n--- Applying / Separating Tests ---\n");
    ac_aspect_t asp;
    /* Body1 faster and ahead: moving away from conjunction (separating) */
    ac_detect_aspect(10.0, 1.0, 5.0, 0.5, AC_ORB_MODERN, &asp);
    FAIL_UNLESS(asp.aspect == AC_ASP_CONJUNCTION, "Conjunction detection for app/sep test");
    FAIL_UNLESS(asp.applying == 0, "Expected separating when faster body ahead");

    /* Body1 faster and behind: moving toward conjunction (applying) */
    ac_detect_aspect(5.0, 1.0, 10.0, 0.5, AC_ORB_MODERN, &asp);
    FAIL_UNLESS(asp.aspect == AC_ASP_CONJUNCTION, "Conjunction detection for app/sep test");
    FAIL_UNLESS(asp.applying == 1, "Expected applying when faster body behind");
}

int main(int argc, char *argv[]) {
    (void)argc; (void)argv;
    printf("Phase 2 Test — Aspect Engine\n");
    printf("============================\n");

    test_orb_thresholds();
    test_known_chart();
    test_applying_separating();

    printf("\n--- RESULT ---\n");
    printf("Passed: %d\n", passed);
    printf("Failed: %d\n", failed);
    if (failed == 0) {
        printf("\nPHASE 2: PASS\n");
        return 0;
    } else {
        printf("\nPHASE 2: FAIL\n");
        return 1;
    }
}
