/*
 * astro_calc.h
 * C FFI wrapper for Swiss Ephemeris
 */
#ifndef ASTRO_CALC_H
#define ASTRO_CALC_H

#define AC_MAX_BODIES 32
#define AC_ERRSTR_LEN 256

/* Return codes */
#define AC_OK 0
#define AC_ERR -1

/* Body IDs matching Swiss Ephemeris sweplan numbers */
#define AC_SUN 0
#define AC_MOON 1
#define AC_MERCURY 2
#define AC_VENUS 3
#define AC_MARS 4
#define AC_JUPITER 5
#define AC_SATURN 6
#define AC_URANUS 7
#define AC_NEPTUNE 8
#define AC_PLUTO 9
#define AC_MEAN_NODE 10
#define AC_TRUE_NODE 11
#define AC_CHIRON 15
#define AC_LILITH 12
#define AC_CERES 17
#define AC_PALLAS 18
#define AC_JUNO 19
#define AC_VESTA 20

typedef struct {
    int body_id;
    char name[32];
    double longitude;
    double latitude;
    double distance;
    double speed;
    int retrograde;
    int sign;
    double sign_degree;
    int house;
} ac_body_t;

typedef struct {
    int house_num;
    double longitude;
    int sign;
    double sign_degree;
} ac_cusp_t;

typedef struct {
    int result;
    char err[AC_ERRSTR_LEN];
    int num_bodies;
    ac_body_t bodies[AC_MAX_BODIES];
    ac_cusp_t cusps[13]; /* 1-12 + ascendant as cusp[0] convention */
    double ascendant;
    double mc;
    double armc;
    double vertex;
} ac_chart_t;


/* Aspect types */
#define AC_ASP_NONE -1
#define AC_ASP_CONJUNCTION 0
#define AC_ASP_SEMISEXTILE 1
#define AC_ASP_SEMISQUARE 2
#define AC_ASP_SEXTILE 3
#define AC_ASP_SQUARE 4
#define AC_ASP_TRINE 5
#define AC_ASP_SESQUIQUADRATE 6
#define AC_ASP_QUINCUNX 7
#define AC_ASP_OPPOSITION 8

/* Orb presets */
#define AC_ORB_CLASSICAL 0
#define AC_ORB_MODERN 1
#define AC_ORB_TIGHT 2
#define AC_ORB_WIDE 3

typedef struct {
    int aspect;          /* AC_ASP_* or AC_ASP_NONE */
    const char *aspect_name;
    double exact_angle;  /* perfect angle for this aspect */
    double actual_angle; /* current angular distance */
    double orb;          /* deviation from exact */
    int applying;        /* 1 = applying, 0 = separating */
} ac_aspect_t;

/* Initialize ephemeris */
int ac_init(const char *ephe_path);
void ac_cleanup(void);

/* Core calculations */
int ac_calc_bodies(double jd_ut, const int *body_ids, int num_bodies, ac_body_t *out);
int ac_calc_houses(double jd_ut, double lat, double lon, char hs, ac_cusp_t *cusps, double *asc, double *mc);

/* Convenience: calculate full chart */
int ac_calc_chart(double jd_ut, double lat, double lon, const int *body_ids, int num_bodies, char hs, ac_chart_t *chart);

/* Date conversion */
double ac_date_to_jd(int year, int month, int day, int hour, int minute, int second, double tz_offset);

const char* ac_sign_name(int sign_num);
const char* ac_body_name(int body_id);
double ac_aspect_angle(double lon1, double lon2);
int ac_detect_aspect(double lon1, double speed1, double lon2, double speed2, int preset, ac_aspect_t *out);

#endif /* ASTRO_CALC_H */
