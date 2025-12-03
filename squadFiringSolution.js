import { WEAPONS } from "./data/weapons.js";
import SquadHeightmap from "./squadHeightmaps.js";
import { Weapon } from "./squadWeapons.js";

export default class SquadFiringSolution {





    /**
     * Generates array with [x,y] dimensions of map, based on the minimap corner transforms from SquadSDK
     * @param {Number[]} fCorner - [x,y] positon of north west corner of minimap in SquadSDK
     * @param {Number[]} sCorner - [x,y] positon of south east corner of minimap in SquadSDK
     * @returns {Number[]} - bounds array with lengths of x and y dimensions of map
     */
    bounds(fCorner, sCorner) {
        // using min and max so that it doesn't matter which corners are used, as long as they are opposite to each other
        const xM = Math.max(fCorner[0], sCorner[0]) - Math.min(fCorner[0], sCorner[0]);
        const yM = Math.max(fCorner[1], sCorner[1]) - Math.min(fCorner[1], sCorner[1]);
        return [xM, yM];
    }

    /**
 * Calculates the final z-scaling of a heightmap,
 * by taking the black and white levels used in gimp to optimize the heightmap,
 * and the zScale of the UE4 landscape transform in meters from SquadSDK
 * @param {number} bLevel - optimized black level from original heightmap
 * @param {number} wLevel - optimized white level from original heightmap
 * @param {number} zScale - original zScale of landscape transform in SquadSDK in meters
 * @returns {number} final scaling
 */
    scale(bLevel, wLevel, zScale) {
        const levelRange = (wLevel - bLevel) / 10000;
        return (512 * levelRange * zScale) / 512;
    }

    constructor(weaponCordinates, targetCordinates, map, heightmap, heightPadding, gravity = 9.78) {

        this.weaponKp = weaponCordinates;
        this.targetKp = targetCordinates;

        this.activeWeapon = new Weapon(
            WEAPONS[0].name,
            WEAPONS[0].velocity,
            WEAPONS[0].deceleration,
            WEAPONS[0].decelerationTime,
            WEAPONS[0].gravityScale,
            WEAPONS[0].minElevation,
            WEAPONS[0].unit,
            WEAPONS[0].logo,
            WEAPONS[0].marker,
            WEAPONS[0].type,
            WEAPONS[0].angleType,
            WEAPONS[0].elevationPrecision,
            WEAPONS[0].minDistance,
            WEAPONS[0].moa,
            WEAPONS[0].explosionDamage,
            WEAPONS[0].explosionRadius[0],
            WEAPONS[0].explosionRadius[1],
            WEAPONS[0].explosionDistanceFromImpact,
            WEAPONS[0].damageFallOff,
            WEAPONS[0].shells,
            WEAPONS[0].heightOffset,
            WEAPONS[0].angleOffset,
            WEAPONS[0].projectileLifespan
        );

        this.map = map;

        map.size = this.bounds(map.SDK_data.minimap.corner0, map.SDK_data.minimap.corner1)[0];
        map.sizeY = this.bounds(map.SDK_data.minimap.corner0, map.SDK_data.minimap.corner1)[1];
        map.scaling = this.scale(
            map.SDK_data?.heightmap?.BWlevels?.[0] ?? 0,
            map.SDK_data?.heightmap?.BWlevels?.[1] ?? 0,
            map.SDK_data?.heightmap?.scale?.[2] ?? 1
        ) || 1;


        this.gameToMapScale = 262 / this.map.size;
        this.gameToMapScaleY = 262 / this.map.sizeY;
        this.mapToGameScale = this.map.size / 262;
        console.log(this.map.size);

        console.log("Map to Game Scale X:", this.mapToGameScale);


        let weaponPos = this.getPos(weaponCordinates);
        let targetPos = this.getPos(targetCordinates);

        weaponPos = { lat: -weaponPos.lng * this.gameToMapScale, lng: weaponPos.lat * this.gameToMapScale };
        targetPos = { lat: -targetPos.lng * this.gameToMapScale, lng: targetPos.lat * this.gameToMapScale };

        this.weaponLatLng = weaponPos;
        this.targetLatLng = targetPos;

        console.log("Weapon LatLng:", this.weaponLatLng);
        console.log("Target LatLng:", this.targetLatLng);


        this.moa = this.degToRad((this.activeWeapon.moa) / 60);
        this.gravity = gravity * this.activeWeapon.gravityScale;
        this.distance = this.getDist();
        this.bearing = this.getBearing(this.weaponLatLng, this.targetLatLng);
        this.velocity = this.activeWeapon.getVelocity(this.distance);

        this.heightMap = heightmap;

        this.weaponHeight = this.heightMap.getHeight(this.weaponLatLng) + parseFloat(heightPadding);
        this.targetHeight = this.heightMap.getHeight(this.targetLatLng);

        console.log("Weapon Height:", this.weaponHeight);
        console.log("Target Height:", this.targetHeight);

        this.heightDiff = this.targetHeight - this.weaponHeight;
        this.elevation = { low: [], high: [] };
        this.elevation.low.rad = this.getElevation(this.distance, true);
        this.elevation.low.deg = this.radToDeg(this.elevation.low.rad);
        this.elevation.low.mil = this.radToMil(this.elevation.low.rad);
        this.elevation.high.rad = this.getElevation(this.distance, false);
        this.elevation.high.deg = this.radToDeg(this.elevation.high.rad);
        this.elevation.high.mil = this.radToMil(this.elevation.high.rad);
        this.timeOfFlight = { low: [], high: [] };
        this.timeOfFlight.low = this.getTimeOfFlight(this.elevation.low.rad);
        this.timeOfFlight.high = this.getTimeOfFlight(this.elevation.high.rad);
        this.spreadParameters = { low: [], high: [] };
        this.spreadParameters.low = this.getSpreadParameter(this.elevation.low.rad, this.timeOfFlight.low);
        this.spreadParameters.high = this.getSpreadParameter(this.elevation.high.rad, this.timeOfFlight.high);

        if (this.timeOfFlight.low > this.activeWeapon.projectileLifespan) this.elevation.low.rad = NaN;
        if (this.timeOfFlight.high > this.activeWeapon.projectileLifespan) this.elevation.high.rad = NaN;
    }


    /**
        * Format keypad input, setting text to uppercase and adding dashes
        * @param {string} text - keypad string to be formatted
        * @returns {string} formatted string
        */
    formatKeyPad(text) {
        const TEXTPARTS = [];

        // If empty string, return
        if (text.length === 0) { return; }

        const TEXTND = text.toUpperCase().split("-").join("");
        TEXTPARTS.push(TEXTND.slice(0, 3));

        // iteration through sub-keypads
        let i = 3;
        while (i < TEXTND.length) {
            TEXTPARTS.push(TEXTND.slice(i, i + 1));
            i += 1;
        }

        return TEXTPARTS.join("-");
    }
    /**
     * Returns the latlng coordinates based on the given keypad string.
     * Supports unlimited amount of sub-keypads.
     * Throws error if keypad string is too short or parsing results in invalid latlng coordinates.
     * @param {string} kp - keypad coordinates, e.g. "A02-3-5-2"
     * @returns {LatLng} converted coordinates
     */
    getPos(kp) {
        const FORMATTED_KEYPAD = this.formatKeyPad(kp);
        const PARTS = FORMATTED_KEYPAD.split("-");
        let interval;
        let lat = 0;
        let lng = 0;
        let i = 0;

        while (i < PARTS.length) {
            if (i === 0) {
                // special case, i.e. letter + number combo
                const LETTERCODE = PARTS[i].charCodeAt(0);
                const LETTERINDEX = LETTERCODE - 65;
                if (PARTS[i].charCodeAt(0) < 65) { return { lat: NaN, lng: NaN }; }
                const KEYPADNB = Number(PARTS[i].slice(1)) - 1;
                lat += 300 * LETTERINDEX;
                lng += 300 * KEYPADNB;

            } else {
                // opposite of calculations in getKP()
                const SUB = Number(PARTS[i]);
                if (Number.isNaN(SUB)) {
                    console.debug(`invalid keypad string: ${FORMATTED_KEYPAD}`);
                }
                const subX = (SUB - 1) % 3;
                const subY = 2 - (Math.ceil(SUB / 3) - 1);

                interval = 300 / 3 ** i;
                lat += interval * subX;
                lng += interval * subY;
            }
            i += 1;
        }

        // at the end, add half of last interval, so it points to the center of the deepest sub-keypad
        interval = 300 / 3 ** (i - 1);
        lat += interval / 2;
        lng += interval / 2;

        return { lat: lat, lng: lng };
    }

    /**
     * Calculate ingame distance between weapon & target
     * https://github.com/sh4rkman/SquadCalc/wiki/Deducing-distance-and-bearing#finding-distance
     * @return {number} - distance in meter
     */
    getDist() {
        const latDelta = (this.targetLatLng.lat - this.weaponLatLng.lat) * -this.mapToGameScale;
        const lngDelta = (this.targetLatLng.lng - this.weaponLatLng.lng) * this.mapToGameScale;
        return Math.hypot(latDelta, lngDelta);
    }

    /**
     * Calculates the angle the mortar needs to be set in order
     * to hit the target at the desired distance and vertical delta.
     * https://github.com/sh4rkman/SquadCalc/wiki/Deducing-Elevation
     * @param {number} [dist] - distance between mortar and target from getDist()
     * @param {boolean} [lowangle] - "high" or "low" angle
     * @returns {number || NaN} radian angle if target in range, NaN otherwise
    */
    getElevation(dist = 0, lowangle = false) {
        let angleFactor;

        const P1 = Math.sqrt(this.velocity ** 4 - this.gravity * (this.gravity * dist ** 2 + 2 * (this.heightDiff - this.activeWeapon.heightOffset) * this.velocity ** 2));
        angleFactor = lowangle ? -P1 : P1;

        let elevation = Math.atan((this.velocity ** 2 + angleFactor) / (this.gravity * dist)) - this.degToRad(this.activeWeapon.angleOffset);

        if (this.radToDeg(elevation) < this.activeWeapon.minElevation[0] || this.radToDeg(elevation) > this.activeWeapon.minElevation[1]) {
            return NaN;
        }

        return elevation;
    }


    /**
     * Calculates the bearing required to see point B from point A.
     * https://github.com/sh4rkman/SquadCalc/wiki/Deducing-distance-and-bearing#finding-bearing
     * @returns {number} - bearing required to see B from A
     */
    getBearing() {
        const latDelta = (this.targetLatLng.lat - this.weaponLatLng.lat) * -this.mapToGameScale;
        const lngDelta = (this.targetLatLng.lng - this.weaponLatLng.lng) * this.mapToGameScale;
        let bearing = Math.atan2(latDelta, lngDelta) * 180 / Math.PI + 90;
        if (bearing < 0) { bearing += 360; } // Avoid Negative Angle by adding a whole rotation
        return bearing;
    }


    /**
     * Calculates the horizontal distance a projectile will travel given a launch angle,
     * initial velocity, and vertical height difference between origin and target.
     * 
     * This function solves the vertical motion equation using the quadratic formula
     * to find the total flight time (t) required to reach the specified height difference.
     * It then uses that time to compute the horizontal distance.
     * 
     * VERY imprecise at low angles and high heights diff
     * 
     * @param {number} angle - Launch angle in degrees (from horizontal).
     * @returns {number} Horizontal distance the projectile will travel (in meters).
     */
    getProjectileDistance(angle) {
        if (this.activeWeapon.name === "Tech.Mortar") angle += 5;

        const angleRad = angle * Math.PI / 180;
        const vx = this.velocity * Math.cos(angleRad);
        const vy = this.velocity * Math.sin(angleRad);

        const a = 0.5 * this.gravity;
        const b = -vy;
        const c = this.heightDiff;

        const discriminant = b * b - 4 * a * c;

        if (discriminant < 0) return 0; // No real solution, target unreachable

        const sqrtDisc = Math.sqrt(discriminant);
        const denom = 2 * a;
        const t1 = (-b + sqrtDisc) / denom;
        const t2 = (-b - sqrtDisc) / denom;

        const t = t1 > 0 ? t1 : (t2 > 0 ? t2 : 0);
        if (t < 0) return 0;

        const distance = vx * t;
        return Math.max(0, distance);
    }


    /**
     * Calculate Axises and angle for spread ellipse
     * @param {number} [elevation] - Elevation angle in radian
     * @param {number} [timeOfFlight] - Time of flight in seconds
     * @returns {object} [semiMajorAxis, semiMinorAxis, ellipseAngle]
     */
    getSpreadParameter(elevation, timeOfFlight) {
        return {
            semiMajorAxis: this.getHorizontalSpread(timeOfFlight),
            semiMinorAxis: this.getVerticalSpread(elevation, this.velocity),
            ellipseAngle: (elevation * (180 / Math.PI))
        };
    }


    /**
     * Calculates the horizontal spread for a given trajectory path length 
     * @param {number} [timeOfFlight] - Time of flight in seconds
     * @returns {number} - Length of horizontal spread in meters
     */
    getHorizontalSpread(timeOfFlight) {
        const horizontalVelocity = Math.sin(this.moa) * this.velocity;
        const horizontalSpread = horizontalVelocity * timeOfFlight;
        return Math.max(0, horizontalSpread);
    }


    /**
     * Calculates the vertical spread of a projectile
     * to hit the target at the desired distance and vertical delta.
     * https://github.com/sh4rkman/SquadCalc/wiki/Deducing-Spread#vertical-spread
     * @param {number} [angle] - angle of the initial shot
     * @returns {number} - vertical spread in meter
     */
    getVerticalSpread(angle) {
        const verticalSpread1 = (this.velocity ** 2 * Math.sin(2 * (angle + (this.moa / 2)))) / this.gravity;
        const verticalSpread2 = (this.velocity ** 2 * Math.sin(2 * (angle - (this.moa / 2)))) / this.gravity;
        const totalSpread = Math.abs(verticalSpread2 - verticalSpread1);
        return Math.max(0, totalSpread);
    }


    /**
     * Calculate the time of flight of the projectile
     * https://github.com/sh4rkman/SquadCalc/wiki/Deducing-Time-Of-Flight
     * @param {number} [angle] - angle of the initial shot in radian
     * @returns {number} - time of flight in seconds
     */
    getTimeOfFlight(angle) {
        // In extreme cases ToF can be NaN (low angle, high heights)
        // if it does just aproximate without taking heights in account this time
        var t = this.velocity * Math.sin(angle) + Math.sqrt((Math.pow(this.velocity, 2) * Math.pow(Math.sin(angle), 2)) + (2 * this.gravity * -this.heightDiff));
        if (isNaN(t)) t = this.velocity * Math.sin(angle) + Math.sqrt((Math.pow(this.velocity, 2) * Math.pow(Math.sin(angle), 2)));
        return t / this.gravity;
    }


    /**
     * Converts radians into degrees
     * @param {number} rad - radians
     * @returns {number} degrees
     */
    radToDeg(rad) {
        return (rad * 180) / Math.PI;
    }


    /**
     * Converts radians into NATO mils
     * @param {number} rad - radians
     * @returns {number} NATO mils
     */
    radToMil(rad) {
        return this.degToMil(this.radToDeg(rad));
    }


    /**
     * Converts degrees to radians
     * @param {number} deg - degrees
     * @returns {number} radians
     */
    degToRad(deg) {
        return (deg * Math.PI) / 180;
    }


    /**
     * Converts degrees into NATO mils
     * @param {number} deg - degrees
     * @returns {number} NATO mils
     */
    degToMil(deg) {
        return deg / (360 / 6400);
    }

    /**
     * Converts NATO mils into degrees
     * @param {number} mil - NATO mils
     * @returns {number} degrees
     */
    milToDeg(mil) {
        return mil * (360 / 6400);
    }

}
