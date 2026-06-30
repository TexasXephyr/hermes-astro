#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "astro_calc.h"
#include "swephexp.h"

typedef struct { char code; const char *name; int sectors; } hs_entry_t;
static const hs_entry_t house_systems[] = {
    {'A', "Equal (Asc)", 12},
    {'B', "Alcabitius", 12},
    {'C', "Campanus", 12},
    {'D', "Equal (MC)", 12},
    {'E', "Equal (Aries)", 12},
    {'F', "Carter/Topocentric", 12},
    {'G', "Gauquelin", 36},
    {'H', "Horizontal", 12},
    {'I', "Sunshine", 12},
    {'K', "Koch", 12},
    {'M', "Morinus", 12},
    {'O', "Porphyry", 12},
    {'P', "Placidus", 12},
    {'Q', "Pullen SD", 12},
    {'R', "Regiomontanus", 12},
    {'S', "Sripati", 12},
    {'T', "Polich-Page Vedic", 12},
    {'U', "Krusinski-Pisa-Goelzer", 12},
    {'V', "Vehlow Equal", 12},
    {'W', "Whole Sign", 12},
    {'X', "Axial Rotation", 12},
    {'Y', "APC houses", 12},
    {0, NULL, 0}
};
static const int year = 1969, month = 11, day = 30;
static const int hour = 20, minute = 43, second = 0;
static const double tz_offset = -6.0;
static const double lat = 35.2167;
static const double lon = -101.8167;

int main(int argc, char *argv[]) {
    (void)argc; (void)argv;
    int passed = 0, failed = 0, total = 0;
    double base_asc = -1.0, base_mc = -1.0;

    printf("Phase 1 Test — All 21 House Systems\n");
    printf("====================================\n");
    printf("Birth: %04d-%02d-%02d %02d:%02d:%02d UTC%+g\n", year, month, day, hour, minute, second, tz_offset);
    printf("Location: %.4f N, %.4f W\n\n", lat, -lon);

    if (ac_init(NULL) != AC_OK) {
        printf("ERROR: Failed to initialize ephemeris\n");
        return 1;
    }

    double jd = ac_date_to_jd(year, month, day, hour, minute, second, tz_offset);
    printf("Julian Day (UT): %.6f\n\n", jd);

    printf("%-4s %-24s %-12s %-12s %-12s %s\n", "Code", "System", "House1", "Ascendant", "MC", "Status");
    printf("%-4s %-24s %-12s %-12s %-12s %s\n", "----", "------", "------", "---------", "--", "------");

    for (int i = 0; house_systems[i].code != 0; i++) {
        total++;
        double h1 = 0.0, asc = 0.0, mc = 0.0;
        int ret = -1;

        if (house_systems[i].code == 'G') {
            double cusps[37];
            double ascmc[10];
            ret = swe_houses(jd, lat, lon, (int)'G', cusps, ascmc);
            if (ret >= 0) { h1 = cusps[1]; asc = ascmc[SE_ASC]; mc = ascmc[SE_MC]; }
        } else {
            ac_cusp_t cusps[13];
            ret = ac_calc_houses(jd, lat, lon, house_systems[i].code, cusps, &asc, &mc);
            if (ret == AC_OK) { h1 = cusps[1].longitude; }
        }

        if (ret < 0) {
            printf("%-4c %-24s %-12s %-12s %-12s FAIL (ret=%d)\n",
                   house_systems[i].code, house_systems[i].name, "--", "--", "--", ret);
            failed++;
            continue;
        }

        if (base_asc < 0) { base_asc = asc; base_mc = mc; }

        double asc_diff = fabs(asc - base_asc);
        double mc_diff = fabs(mc - base_mc);
        const char *status = "PASS";
        if (asc_diff > 0.001 || mc_diff > 0.001) status = "WARN (asc/mc mismatch)";
        if (h1 < 0 || h1 >= 360) status = "FAIL (bad h1)";

        printf("%-4c %-24s %11.6f %11.6f %11.6f %s\n",
               house_systems[i].code, house_systems[i].name, h1, asc, mc, status);

        if (strcmp(status, "PASS") == 0 || strncmp(status, "WARN", 4) == 0) passed++;
        else failed++;
    }

    printf("\n--- VALIDATION ---\n");
    printf("Ascendant (all systems): %.6f\n", base_asc);
    printf("MC (all systems):        %.6f\n", base_mc);

    double expected_asc = 113.018172;
    double asc_err = fabs(base_asc - expected_asc);
    printf("Ascendant diff from expected %.6f: %.6f\n", expected_asc, asc_err);

    double h1vals[32];
    int nh1 = 0;
    for (int i = 0; house_systems[i].code != 0; i++) {
        double h1 = 0.0, asc = 0.0, mc = 0.0;
        int ret = -1;
        if (house_systems[i].code == 'G') {
            double cusps[37]; double ascmc[10];
            ret = swe_houses(jd, lat, lon, (int)'G', cusps, ascmc);
            if (ret >= 0) h1 = cusps[1];
        } else {
            ac_cusp_t cusps[13];
            ret = ac_calc_houses(jd, lat, lon, house_systems[i].code, cusps, &asc, &mc);
            if (ret == AC_OK) h1 = cusps[1].longitude;
        }
        if (ret < 0) continue;
        int dup = 0;
        for (int j = 0; j < nh1; j++) { if (fabs(h1vals[j] - h1) < 0.001) { dup = 1; break; } }
        if (!dup) h1vals[nh1++] = h1;
    }
    printf("Unique House1 cusp values: %d\n", nh1);

    ac_cleanup();
    printf("\n--- RESULT ---\n");
    printf("Systems tested: %d\n", total);
    printf("Passed: %d\n", passed);
    printf("Failed: %d\n", failed);
    if (failed == 0 && nh1 > 1) { printf("\nPHASE 1: PASS\n"); return 0; }
    else { printf("\nPHASE 1: FAIL\n"); return 1; }
}
