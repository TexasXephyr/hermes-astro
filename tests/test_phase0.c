/*
 * test_phase0.c
 * Basic test: Calculate Xephyr's natal chart
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "astro_calc.h"

int main(int argc, char *argv[]) {
    (void)argc; (void)argv;
    
    ac_chart_t chart;
    int bodies[] = {
        AC_SUN, AC_MOON, AC_MERCURY, AC_VENUS, AC_MARS,
        AC_JUPITER, AC_SATURN, AC_URANUS, AC_NEPTUNE, AC_PLUTO,
        AC_CHIRON, AC_MEAN_NODE, AC_LILITH
    };
    int num_bodies = sizeof(bodies) / sizeof(bodies[0]);
    
    /* Xephyr's birth data from second-brain */
    int year = 1969, month = 11, day = 30;
    int hour = 20, minute = 43, second = 0;
    double tz_offset = -6.0;  /* CST */
    double lat = 35.2211;      /* Amarillo TX approximate */
    double lon = -101.8313;    /* Amarillo TX approximate */
    /* More precise: Amarillo TX is ~35.2211°N, 101.8313°W */
    /* Actually, from notes: Amarillo TX (35.2167, -101.8167) */
    lat = 35.2167;
    lon = -101.8167;
    
    printf("Phase 0 Test — Xephyr Natal Chart\n");
    printf("===================================\n");
    printf("Birth: %04d-%02d-%02d %02d:%02d:%02d UTC%+g\n", 
           year, month, day, hour, minute, second, tz_offset);
    printf("Location: %.4f°N, %.4f°W\n\n", lat, -lon);
    
    /* Initialize */
    if (ac_init(NULL) != AC_OK) {
        printf("ERROR: Failed to initialize ephemeris\n");
        return 1;
    }
    printf("Ephemeris initialized (Moshier built-in)\n\n");
    
    /* Convert to Julian Day */
    double jd = ac_date_to_jd(year, month, day, hour, minute, second, tz_offset);
    printf("Julian Day (UT): %.6f\n\n", jd);
    
    /* Calculate full chart */
    char hs = 'K';  /* Koch house system */
    int ret = ac_calc_chart(jd, lat, lon, bodies, num_bodies, hs, &chart);
    
    if (ret != AC_OK) {
        printf("ERROR: Chart calculation failed: %s\n", chart.err);
        ac_cleanup();
        return 1;
    }
    
    printf("Bodies:\n");
    printf("%-12s %-12s %-20s %-8s %-8s %s\n",
           "Body", "Longitude", "Sign", "Degree", "Speed", "Retro");
    printf("%-12s %-12s %-20s %-8s %-8s %s\n",
           "----", "---------", "----", "------", "-----", "-----");
    
    for (int i = 0; i < num_bodies; i++) {
        printf("%-12s %11.6f°  %-20s %7.3f°  %6.4f°   %s\n",
               chart.bodies[i].name,
               chart.bodies[i].longitude,
               ac_sign_name(chart.bodies[i].sign),
               chart.bodies[i].sign_degree,
               chart.bodies[i].speed,
               chart.bodies[i].retrograde ? "R" : "D");
    }
    
    printf("\n");
    printf("Houses (Koch):\n");
    printf("%-8s %-12s %-12s %-8s\n", "House", "Cusp", "Sign", "Degree");
    printf("%-8s %-12s %-12s %-8s\n", "-----", "----", "----", "------");
    
    for (int i = 1; i <= 12; i++) {
        printf("%-8d %11.6f°  %-12s %7.3f°\n",
               chart.cusps[i].house_num,
               chart.cusps[i].longitude,
               ac_sign_name(chart.cusps[i].sign),
               chart.cusps[i].sign_degree);
    }
    printf("\nAscendant: %.6f° (%s %.3f°)\n", chart.ascendant,
           ac_sign_name((int)(fmod(chart.ascendant, 360.0)/30.0)),
           fmod(fmod(chart.ascendant, 360.0), 30.0));
    printf("MC:        %.6f° (%s %.3f°)\n", chart.mc,
           ac_sign_name((int)(fmod(chart.mc, 360.0)/30.0)),
           fmod(fmod(chart.mc, 360.0), 30.0));
    
    /* Validation: Sun should be ~8.74° Sagittarius = ~248.74° */
    double sun_lon = 0;
    for (int i = 0; i < num_bodies; i++) {
        if (chart.bodies[i].body_id == AC_SUN) {
            sun_lon = chart.bodies[i].longitude;
            break;
        }
    }
    
    printf("\n--- VALIDATION ---\n");
    printf("Sun longitude: %.6f°\n", sun_lon);
    printf("Expected: ~248.74° (8.74° Sagittarius)\n");
    double expected = 248.736218; /* From audit manual verification */
    double diff = fabs(sun_lon - expected);
    printf("Difference: %.6f°\n", diff);
    
    if (diff < 1.0) {
        printf("\nPASS: Sun position within 1° of expected (%.2f')\n", diff * 60);
    } else {
        printf("\nFAIL: Sun position off by %.2f°\n", diff);
    }
    
    if (diff < 0.001) {
        printf("PASS: Arc-second precision achieved\n");
    }
    
    /* Also check Ascendant matches audit value */
    double expected_asc = 293.017; /* 23° Cancer = 90° + 23.017° = 113.017° wait... */
    /* Cancer = sign 3, 3 * 30 = 90. 90 + 23.017 = 113.017 */
    printf("\nAscendant: %.6f°\n", chart.ascendant);
    expected_asc = 90.0 + 23.017;
    double asc_diff = fabs(chart.ascendant - expected_asc);
    printf("Expected Asc: ~%.3f° (23° Cancer)\n", expected_asc);
    printf("Asc Difference: %.6f°\n", asc_diff);
    if (asc_diff < 1.0) {
        printf("PASS: Ascendant within 1°\n");
    } else {
        printf("FAIL: Ascendant off by %.2f°\n", asc_diff);
    }
    
    ac_cleanup();
    return (diff < 1.0 && asc_diff < 1.0) ? 0 : 1;
}
