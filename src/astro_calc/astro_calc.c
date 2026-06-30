/*
 * astro_calc.c
 * C FFI wrapper for Swiss Ephemeris
 */
#include <string.h>
#include <stdlib.h>
#include <math.h>
#include "astro_calc.h"

/* Swiss Ephemeris headers are in a different location during build */
#include <swephexp.h>

/*
 * Sign names — 0=Aries to 11=Pisces
 */
static const char *sign_names[] = {
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces"
};

/*
 * Body names for common IDs
 */
static const struct {
    int id;
    const char *name;
} body_names[] = {
    {AC_SUN, "Sun"},
    {AC_MOON, "Moon"},
    {AC_MERCURY, "Mercury"},
    {AC_VENUS, "Venus"},
    {AC_MARS, "Mars"},
    {AC_JUPITER, "Jupiter"},
    {AC_SATURN, "Saturn"},
    {AC_URANUS, "Uranus"},
    {AC_NEPTUNE, "Neptune"},
    {AC_PLUTO, "Pluto"},
    {AC_MEAN_NODE, "Mean Node"},
    {AC_TRUE_NODE, "True Node"},
    {AC_LILITH, "Lilith"},
    {AC_CHIRON, "Chiron"},
    {AC_CERES, "Ceres"},
    {AC_PALLAS, "Pallas"},
    {AC_JUNO, "Juno"},
    {AC_VESTA, "Vesta"},
    {-1, NULL}
};

/* ================================================================ */

int ac_init(const char *ephe_path) {
    if (ephe_path && ephe_path[0]) {
        swe_set_ephe_path((char*)ephe_path);
    } else {
        /* Use Moshier built-in ephemeris */
        swe_set_ephe_path(NULL);
    }
    return AC_OK;
}

void ac_cleanup(void) {
    swe_close();
}

const char* ac_sign_name(int sign_num) {
    if (sign_num < 0 || sign_num > 11) return "Unknown";
    return sign_names[sign_num];
}

const char* ac_body_name(int body_id) {
    for (int i = 0; body_names[i].name != NULL; i++) {
        if (body_names[i].id == body_id) {
            return body_names[i].name;
        }
    }
    return "Unknown";
}

/* ================================================================ */

static void parse_result(double lon, double *sign_num, double *sign_deg) {
    *sign_num = (int)(fmod(fmod(lon, 360.0) + 360.0, 360.0) / 30.0);
    *sign_deg = fmod(fmod(lon, 360.0) + 360.0, 30.0);
}

int ac_calc_bodies(double jd_ut, const int *body_ids, int num_bodies, ac_body_t *out) {
    char err[AS_MAXCH];
    double x[6];
    int32 iflag = SEFLG_SPEED;
    
    for (int i = 0; i < num_bodies; i++) {
        int ret = swe_calc_ut(jd_ut, body_ids[i], iflag, x, err);
        if (ret < 0) {
            /* Some bodies may not be available in Moshier ephemeris */
            ret = swe_calc_ut(jd_ut, body_ids[i], SEFLG_SPEED, x, err);
            if (ret < 0) {
                strncpy(out[i].name, ac_body_name(body_ids[i]), 31);
                out[i].name[31] = '\0';
                out[i].body_id = body_ids[i];
                out[i].longitude = 0.0;
                continue;
            }
        }
        
        strncpy(out[i].name, ac_body_name(body_ids[i]), 31);
        out[i].name[31] = '\0';
        out[i].body_id = body_ids[i];
        out[i].longitude = x[0];      /* ecliptic longitude */
        out[i].latitude = x[1];       /* ecliptic latitude */
        out[i].distance = x[2];         /* distance in AU */
        out[i].speed = x[3];            /* daily speed in longitude */
        out[i].retrograde = (x[3] < 0) ? 1 : 0;
        
        double sn, sd;
        parse_result(x[0], &sn, &sd);
        out[i].sign = (int)sn;
        out[i].sign_degree = sd;
    }
    
    return AC_OK;
}

int ac_calc_houses(double jd_ut, double lat, double lon, char hs,
                   ac_cusp_t *cusps, double *asc, double *mc) {
    /* Gauquelin ('G') returns 36 sectors via swe_houses, need 37-element buffer */
    double cusps_arr[37];
    double ascmc[10];
    int ret = swe_houses(jd_ut, lat, lon, (int)hs, cusps_arr, ascmc);
    
    if (ret < 0) return AC_ERR;
    
    /* For standard systems cusps_arr[1..12] = house cusps 1-12.
     * For Gauquelin ('G') cusps_arr[1..36] = 36 sectors.
     * We only populate cusps[1..12] to fit ac_cusp_t[13] safely. */
    for (int i = 1; i <= 12; i++) {
        cusps[i].house_num = i;
        cusps[i].longitude = cusps_arr[i];
        double sn, sd;
        parse_result(cusps_arr[i], &sn, &sd);
        cusps[i].sign = (int)sn;
        cusps[i].sign_degree = sd;
    }
    
    if (asc) *asc = ascmc[SE_ASC];
    if (mc) *mc = ascmc[SE_MC];
    
    return AC_OK;
}

int ac_calc_chart(double jd_ut, double lat, double lon,
                  const int *body_ids, int num_bodies, char hs, ac_chart_t *chart) {
    memset(chart, 0, sizeof(*chart));
    
    chart->result = ac_calc_bodies(jd_ut, body_ids, num_bodies, chart->bodies);
    if (chart->result != AC_OK) {
        snprintf(chart->err, AC_ERRSTR_LEN, "Body calculation failed");
        return chart->result;
    }
    chart->num_bodies = num_bodies;
    
    chart->result = ac_calc_houses(jd_ut, lat, lon, hs, chart->cusps, &chart->ascendant, &chart->mc);
    if (chart->result != AC_OK) {
        snprintf(chart->err, AC_ERRSTR_LEN, "House calculation failed");
        return chart->result;
    }
    
    /* Assign houses to bodies (simple: which cusp is body closest to?) */
    for (int b = 0; b < num_bodies; b++) {
        double blon = chart->bodies[b].longitude;
        for (int h = 1; h <= 12; h++) {
            double c1 = chart->cusps[h].longitude;
            double c2 = chart->cusps[(h % 12) + 1].longitude;
            /* Check if body is in this house sector */
            double dc1 = fmod(blon - c1 + 360.0, 360.0);
            double dc2 = fmod(c2 - c1 + 360.0, 360.0);
            if (dc1 < dc2) {
                chart->bodies[b].house = h;
                break;
            }
        }
    }
    
    return AC_OK;
}

/* ================================================================ */

double ac_date_to_jd(int year, int month, int day, int hour, int minute, int second, double tz_offset) {
    double ut = hour + minute / 60.0 + second / 3600.0;
    ut -= tz_offset;  /* Convert local to UT */
    return swe_julday(year, month, day, ut, SE_GREG_CAL);
}

/* ================================================================ */

double ac_aspect_angle(double lon1, double lon2) {
    double diff = fabs(lon1 - lon2);
    while (diff > 180.0) diff = 360.0 - diff;
    return diff;
}


/* ================================================================ */
/* Aspect engine */

static const struct {
    int aspect;
    const char *name;
    double angle;
} aspect_defs[] = {
    {AC_ASP_CONJUNCTION,    "Conjunction",    0.0},
    {AC_ASP_SEMISEXTILE,    "Semisextile",    30.0},
    {AC_ASP_SEMISQUARE,     "Semisquare",     45.0},
    {AC_ASP_SEXTILE,        "Sextile",        60.0},
    {AC_ASP_SQUARE,         "Square",         90.0},
    {AC_ASP_TRINE,          "Trine",          120.0},
    {AC_ASP_SESQUIQUADRATE, "Sesquiquadrate", 135.0},
    {AC_ASP_QUINCUNX,       "Quincunx",       150.0},
    {AC_ASP_OPPOSITION,     "Opposition",     180.0},
    {-1, NULL, 0.0}
};

static const double orb_table[9][4] = {
    /* Classical, Modern, Tight, Wide */
    [AC_ASP_CONJUNCTION]    = {6.0, 8.0, 2.0, 10.0},
    [AC_ASP_SEMISEXTILE]    = {1.0, 2.0, 0.5, 3.0},
    [AC_ASP_SEMISQUARE]     = {1.0, 2.0, 0.5, 3.0},
    [AC_ASP_SEXTILE]        = {3.0, 4.0, 1.0, 6.0},
    [AC_ASP_SQUARE]         = {4.0, 6.0, 1.0, 8.0},
    [AC_ASP_TRINE]          = {4.0, 6.0, 1.0, 8.0},
    [AC_ASP_SESQUIQUADRATE] = {1.0, 2.0, 0.5, 3.0},
    [AC_ASP_QUINCUNX]       = {1.0, 2.0, 0.5, 3.0},
    [AC_ASP_OPPOSITION]     = {6.0, 8.0, 2.0, 10.0},
};

int ac_detect_aspect(double lon1, double speed1, double lon2, double speed2, int preset, ac_aspect_t *out) {
    if (preset < 0 || preset > 3) preset = AC_ORB_MODERN;
    
    double actual = ac_aspect_angle(lon1, lon2);
    int best = AC_ASP_NONE;
    double best_orb = 1e9;
    double exact = 0.0;
    const char *name = NULL;
    
    for (int i = 0; aspect_defs[i].aspect != -1; i++) {
        int asp = aspect_defs[i].aspect;
        double orb = fabs(actual - aspect_defs[i].angle);
        double allowed = orb_table[asp][preset];
        if (orb < allowed - 1e-9 && orb < best_orb) {
            best = asp;
            best_orb = orb;
            exact = aspect_defs[i].angle;
            name = aspect_defs[i].name;
        }
    }
    
    if (best == AC_ASP_NONE) {
        memset(out, 0, sizeof(*out));
        out->aspect = AC_ASP_NONE;
        out->aspect_name = "None";
        return AC_OK;
    }
    
    out->aspect = best;
    out->aspect_name = name;
    out->exact_angle = exact;
    out->actual_angle = actual;
    out->orb = best_orb;
    
    double future = ac_aspect_angle(lon1 + speed1, lon2 + speed2);
    out->applying = (future < actual - 1e-9) ? 1 : 0;
    
    return AC_OK;
}

