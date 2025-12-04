// /**
//  * KP Calculator Module
//  * Converts KP grid coordinates to lat/lng and calculates firing solutions
//  */

import { MAPS } from "./data/maps.js";
import SquadFiringSolution from "./squadFiringSolution.js";
import SquadHeightmap from "./squadHeightmaps.js";
import fs from 'fs';

/**
 * Pretty print firing solution to console
 * @param {object} result - Result from calculateFromKP
 */
function printFiringSolution(result) {
    console.log("\n╔══════════════════════════════════════╗");
    console.log("║      SQUADCALC - ATEŞ ÇÖZÜMÜ        ║");
    console.log("╚══════════════════════════════════════╝");

    console.log("\n📍 KONUM BİLGİLERİ:");
    console.log(`   Silah Konumu  : ${result.weapon.kp} | Height: ${result.weapon.coordinates.lat}, ${result.weapon.coordinates.lng}`);
    console.log(`   Hedef Konumu  : ${result.target.kp}` + ` | Height: ${result.target.coordinates.lat}, ${result.target.coordinates.lng}`);
    console.log(`   Harita        : ${result.map.name} (${result.map.size})`);

    console.log("\n🎯 BALİSTİK BİLGİLER:");
    console.log(`   Mesafe        : ${result.ballistics.distance}`);
    console.log(`   Yön (Bearing) : ${result.ballistics.bearing}`);
    console.log(`   Yükseklik Farkı: ${result.ballistics.heightDiff}`);

    console.log("\n📐 DÜŞÜK AÇI (Low Angle):");
    console.log(`   Yükseliş      : ${result.ballistics.lowAngle.elevation.degrees} | ${result.ballistics.lowAngle.elevation.mils}`);
    console.log(`   Uçuş Süresi   : ${result.ballistics.lowAngle.timeOfFlight}`);
    console.log(`   Dağılım       : ${result.ballistics.lowAngle.spread.horizontal} x ${result.ballistics.lowAngle.spread.vertical}`);

    console.log("\n📐 YÜKSEK AÇI (High Angle):");
    console.log(`   Yükseliş      : ${result.ballistics.highAngle.elevation.degrees} | ${result.ballistics.highAngle.elevation.mils}`);
    console.log(`   Uçuş Süresi   : ${result.ballistics.highAngle.timeOfFlight}`);
    console.log(`   Dağılım       : ${result.ballistics.highAngle.spread.horizontal} x ${result.ballistics.highAngle.spread.vertical}`);

    console.log("\n🔫 SİLAH BİLGİSİ:");
    console.log(`   Silah         : ${result.weapon_info.name}`);
    console.log(`   Hız           : ${result.weapon_info.velocity}`);
    console.log(`   Tip           : ${result.weapon_info.type}`);
    console.log("\n════════════════════════════════════════\n");

    //write datas to json file like azimuth,elevation,distance,time of flight etc.
    fs.writeFileSync('firing_solution.json', JSON.stringify(result, null, 2));
}



let TargetsCordinates = fs.readFileSync('targets_coordinates.json');
const targets = JSON.parse(TargetsCordinates);

let map = MAPS[1];//ANVIL


let heightMap = new SquadHeightmap(map);



let ms = 2000;
setTimeout(() => {

    // Calculate firing solution
    const firingSolution = new SquadFiringSolution(
        targets.weaponKp,
        targets.targetKp,
        map,
        heightMap,
        0,
    );




    // Format output
    const result = {
        weapon: {
            kp: firingSolution.weaponKp,
            coordinates: firingSolution.weaponLatLng,
            height: firingSolution.weaponHeight
        },
        target: {
            kp: firingSolution.targetKp,
            coordinates: firingSolution.targetLatLng,
            height: firingSolution.targetHeight
        },
        ballistics: {
            distance: firingSolution.distance.toFixed(1) + "m",
            bearing: firingSolution.bearing.toFixed(1) + "°",
            heightDiff: firingSolution.heightDiff.toFixed(1) + "m",
            lowAngle: {
                elevation: {
                    degrees: firingSolution.elevation.low.deg?.toFixed(2) + "°" || "---",
                    mils: firingSolution.elevation.low.mil?.toFixed(1) + " mil" || "---",
                    radians: firingSolution.elevation.low.rad || NaN
                },
                timeOfFlight: firingSolution.timeOfFlight.low?.toFixed(1) + "s" || "---",
                spread: {
                    horizontal: firingSolution.spreadParameters.low.semiMajorAxis?.toFixed(1) + "m",
                    vertical: firingSolution.spreadParameters.low.semiMinorAxis?.toFixed(1) + "m"
                }
            },
            highAngle: {
                elevation: {
                    degrees: firingSolution.elevation.high.deg?.toFixed(2) + "°" || "---",
                    mils: firingSolution.elevation.high.mil?.toFixed(1) + " mil" || "---",
                    radians: firingSolution.elevation.high.rad || NaN
                },
                timeOfFlight: firingSolution.timeOfFlight.high?.toFixed(1) + "s" || "---",
                spread: {
                    horizontal: firingSolution.spreadParameters.high.semiMajorAxis?.toFixed(1) + "m",
                    vertical: firingSolution.spreadParameters.high.semiMinorAxis?.toFixed(1) + "m"
                }
            }
        },
        weapon_info: {
            name: firingSolution.activeWeapon.name,
            velocity: firingSolution.activeWeapon.velocity + " m/s",
            type: firingSolution.activeWeapon.type
        },
        map: {
            name: firingSolution.map.name,
            size: firingSolution.map.size + "m x " + firingSolution.map.sizeY + "m"
        }
    };

    printFiringSolution(result);


}, ms);
