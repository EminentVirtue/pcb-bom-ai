
import { Asset } from './playcanvas.mjs'

/**
 * @name loadGlbContainerFromAsset
 * @function
 * @description Load a GLB container from a binary asset that is a GLB. If the asset is not loaded yet, it will load the asset.
 * @param {pc.Asset} glbBinAsset The binary asset that is the GLB.
 * @param {Object} options Optional. Extra options to do extra processing on the GLB.
 * @param {String} assetName - Name of the asset.
 * @param {pc.AppBase} app - The application instance
 * If `error` is null, then the load is successful.
 * @returns {Promise<pc.Asset>} The asset that is created for the container resource.
 */
export const loadGlbContainerFromAsset = function (glbBinAsset, options, assetName, app) {
    return new Promise((resolve, reject) => {
        glbBinAsset.ready(async (asset) => {
            const blob = new Blob([asset.resource]);
            const data = URL.createObjectURL(blob);
            const containerAsset = await loadGlbContainerFromUrl(data, options, assetName, app)
            URL.revokeObjectURL(data);
            resolve(containerAsset);
        });
        app.assets.load(glbBinAsset);
    })
};

/**
 * @name loadGlbContainerFromUrl
 * @function
 * @description Load a GLB container from a URL that returns a `model/gltf-binary` as a GLB.
 * @param {String} url - The URL for the GLB
 * @param {Object?} options - Extra options to do extra processing on the GLB.
 * @param {String} assetName - Name of the asset.
 * @param {pc.AppBase} app -  The application instance
 * @returns {Promise<pc.Asset>} The asset that is created for the container resource.
 */
export const loadGlbContainerFromUrl = function (url, options, assetName, app) {

    return new Promise((resolve, reject) => {
        const filename = assetName + '.glb';
        const file = {
            url: url,
            filename: filename
        };

        const asset = new Asset(filename, 'container', file, null, options);
        asset.once('load', function (containerAsset) {
            // As we play animations by name, if we have only one animation, keep it the same name as
            // the original container otherwise, postfix it with a number
            let animations = containerAsset.resource.animations;
            if (animations.length == 1) {
                animations[0].name = assetName;
            } else if (animations.length > 1) {
                for (let i = 0; i < animations.length; ++i) {
                    animations[i].name = assetName + ' ' + i.toString();
                }
            }
            console.log('resrs')
            resolve(containerAsset);
        });

        app.assets.add(asset);
        app.assets.load(asset);

    })
};