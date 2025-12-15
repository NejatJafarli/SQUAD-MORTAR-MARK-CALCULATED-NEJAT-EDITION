


// const MORTAR_LOC = $("#mortar-location");

import { MAPS } from "./data/maps.js";
import SquadFiringSolution from "./squadFiringSolutionOld.js";
import SquadHeightmap from "./squadHeightmaps.js";
import fs from 'fs';




class MortarCalculator {


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

    constructor(minimap) {
        this.map = minimap;

        this.map.size = this.bounds(this.map.SDK_data.minimap.corner0, this.map.SDK_data.minimap.corner1)[0];
        this.map.sizeY = this.bounds(this.map.SDK_data.minimap.corner0, this.map.SDK_data.minimap.corner1)[1];
        this.map.scaling = this.scale(
            this.map.SDK_data?.heightmap?.BWlevels?.[0] ?? 0,
            this.map.SDK_data?.heightmap?.BWlevels?.[1] ?? 0,
            this.map.SDK_data?.heightmap?.scale?.[2] ?? 1
        ) || 1;


        this.map.gameToMapScale = 256 / this.map.size;
        this.map.gameToMapScaleY = 256 / this.map.sizeY;
        this.map.mapToGameScale = this.map.size / 256;

        this.heightMap = new SquadHeightmap(this.map);
    }


    shoot(mortarKP, targetKP) {
        const a = mortarKP;
        const b = targetKP;
        let aPos;
        let bPos;

        aPos = this.getPos(a);
        bPos = this.getPos(b);

        if (Number.isNaN(aPos.lng) || Number.isNaN(bPos.lng)) {
            if (Number.isNaN(aPos.lng) && Number.isNaN(bPos.lng)) {
                // this.showError(`<div data-i18n='common:invalidMortarTarget'>${i18next.t("common:invalidMortarTarget")}</div>`);
                console.log(`<div data-i18n='common:invalidMortarTarget'>${i18next.t("common:invalidMortarTarget")}</div>`);
            } else if (Number.isNaN(aPos.lng)) {
                // this.showError(`<div data-i18n='common:invalidMortar'>${i18next.t("common:invalidMortar")}</div>`, "mortar");
                console.log(`<div data-i18n='common:invalidMortar'>${i18next.t("common:invalidMortar")}</div>`);
            } else {
                // this.showError(`<div data-i18n='common:invalidTarget'>${i18next.t("common:invalidTarget")}</div>`, "target");
                console.log(`<div data-i18n='common:invalidTarget'>${i18next.t("common:invalidTarget")}</div>`);
            }
            return 1;
        }

        aPos = { lat: -aPos.lng * this.map.gameToMapScale, lng: aPos.lat * this.map.gameToMapScale };
        bPos = { lat: -bPos.lng * this.map.gameToMapScale, lng: bPos.lat * this.map.gameToMapScale };

        let firingSolution = new SquadFiringSolution(aPos, bPos, this.map, 0, this.heightMap);

        return firingSolution;
    }
}


//foreach maps find name ==Jensen

let map = MAPS.find(m => m.name === "Jensen");


// Initialize MortarCalculator once
let MortarCalculatorObj = new MortarCalculator(map);
console.log("Mortar Calculator initialized for Yehorivka map");

// Store last coordinates to detect changes
let lastPlayerCoord = null;
let lastMarkerCoord = null;

/**
 * Read coordinates from JSON file and calculate firing solution
 */
function calculateFiringSolution() {
    try {
        // Read coordinates file
        const data = fs.readFileSync('coordinates.json', 'utf8');
        const coords = JSON.parse(data);

        const playerCoord = coords.player?.full;
        const markerCoord = coords.marker?.full;

        // Check if coordinates are valid
        if (!playerCoord || !markerCoord) {
            console.log("Waiting for valid coordinates...");
            return;
        }

        // Check if coordinates changed
        if (playerCoord === lastPlayerCoord && markerCoord === lastMarkerCoord) {
            // No change, skip calculation
            return;
        }

        // Update last known coordinates
        lastPlayerCoord = playerCoord;
        lastMarkerCoord = markerCoord;

        console.log(`\n${"=".repeat(50)}`);
        console.log(`New coordinates detected:`);
        console.log(`  Player: ${playerCoord}`);
        console.log(`  Marker: ${markerCoord}`);

        // Calculate firing solution
        let res = MortarCalculatorObj.shoot(playerCoord, markerCoord);

        if (res === 1) {
            console.log("Invalid coordinates - calculation failed");
            return;
        }

        // Extract elevation and bearing
        let elevation = res.activeWeapon.getAngleType() === -1 ? res.elevation.high : res.elevation.low;
        elevation = res.activeWeapon.unit === "mil" ? elevation.mil : elevation.deg;
        let bearing = res.bearing;

        // Round values
        // elevation = Math.round(elevation * 10) / 10;
        // bearing = Math.round(bearing * 10) / 10;

        console.log(`\nFiring Solution:`);
        console.log(`  Elevation: ${elevation} ${res.activeWeapon.unit}`);
        console.log(`  Bearing: ${bearing}°`);
        console.log(`${"=".repeat(50)}\n`);

        // Save firing solution to JSON file
        const firingSolutionData = {
            timestamp: new Date().toISOString(),
            player: playerCoord,
            marker: markerCoord,
            elevation: elevation,
            elevationUnit: res.activeWeapon.unit,
            bearing: bearing,
            distance: Math.round(res.distance * 10) / 10
        };

        fs.writeFileSync('firing_solution.json', JSON.stringify(firingSolutionData, null, 4), 'utf8');
        console.log("✓ Firing solution saved to firing_solution.json");

    } catch (error) {
        if (error.code === 'ENOENT') {
            console.log("Waiting for coordinates.json file...");
        } else {
            console.error("Error reading coordinates:", error.message);
        }
    }
}

// Run calculation every second
console.log("Starting coordinate monitoring (checking every 1 second)...\n");
setInterval(calculateFiringSolution, 1000);

