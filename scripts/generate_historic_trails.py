#!/usr/bin/env python3
"""Generate historic trails GeoJSON and landmarks JSON for the Prescia Maps project.

Writes two files to the output directory:
  - historic_trails.geojson
  - historic_trail_landmarks.json
"""

import argparse
import json
import os
import urllib.request

TRAILS = [
    {
        "name": "Oregon Trail",
        "years": "1830s-1869",
        "description": "The most heavily traveled overland route in American history, the Oregon Trail carried over 400,000 emigrants from Missouri to the Pacific Northwest between the 1840s and 1860s. It followed the Platte River valley through the Great Plains before crossing the Continental Divide at South Pass.",
        "coordinates": [[-94.5786,39.0997],[-97.0000,40.7000],[-98.3820,40.6936],[-100.4500,41.3200],[-104.5450,42.2125],[-105.9000,42.9400],[-108.8600,42.5000],[-112.4455,42.8713],[-115.7000,42.6000],[-116.2000,43.6500],[-116.9347,43.6000],[-118.9647,45.5946],[-121.1789,45.6052],[-122.6765,45.5231]]
    },
    {
        "name": "California Trail",
        "years": "1841-1869",
        "description": "Branching from the Oregon Trail at South Pass or Fort Hall, the California Trail brought hundreds of thousands of emigrants and Forty-Niners to the goldfields of California. The treacherous crossing of the Sierra Nevada, especially at Donner Pass, became legendary for its dangers.",
        "coordinates": [[-108.8600,42.5000],[-112.4455,42.8713],[-113.7150,42.0706],[-115.7271,42.6000],[-117.0000,40.7000],[-118.0000,40.5000],[-118.7000,39.3000],[-119.8138,39.5296],[-120.9000,38.8000],[-121.4944,38.5816]]
    },
    {
        "name": "Santa Fe Trail",
        "years": "1821-1880",
        "description": "Opened by William Becknell in 1821 following Mexican independence from Spain, the Santa Fe Trail was the great commercial highway linking Missouri to the Mexican Southwest. For nearly 60 years it carried merchant caravans, military expeditions, and eventually stagecoaches through the southern plains.",
        "coordinates": [[-94.5786,39.0997],[-96.4892,38.6617],[-98.0000,38.3000],[-99.3295,38.2500],[-100.6667,37.9900],[-102.5000,37.9800],[-103.5500,37.4900],[-104.4000,37.2000],[-104.5000,36.9100],[-105.9378,35.6870]]
    },
    {
        "name": "Mormon Trail",
        "years": "1846-1869",
        "description": "Blazed by Brigham Young and the Latter-day Saints fleeing religious persecution in 1846-1847, the Mormon Trail paralleled the Oregon Trail but ran along the north bank of the Platte River. Over 70,000 Mormon pioneers followed this route to build their Zion in the Salt Lake Valley.",
        "coordinates": [[-91.3810,40.5500],[-93.0000,41.2500],[-95.8517,41.2606],[-97.0000,41.5000],[-99.0000,41.1000],[-101.0000,41.2000],[-104.5450,42.2125],[-107.0000,42.1000],[-110.3874,41.3166],[-111.3874,40.7608]]
    },
    {
        "name": "Pony Express Route",
        "years": "1860-1861",
        "description": "The Pony Express operated for only 18 months from April 1860 to October 1861, yet became one of the most celebrated enterprises in American history. Riders covered the nearly 2,000-mile route between Missouri and California in approximately 10 days, delivering mail across the continent before the telegraph made the service obsolete.",
        "coordinates": [[-94.8467,39.7675],[-96.0000,40.1000],[-98.3820,40.6936],[-100.4500,40.6900],[-102.2583,40.9875],[-104.5450,42.2125],[-107.0000,42.1000],[-110.3874,41.3166],[-111.3874,40.7608],[-114.0000,39.2000],[-116.2023,39.1638],[-119.7500,39.1500],[-121.4944,38.5816]]
    },
    {
        "name": "Natchez Trace",
        "years": "1700s-1820s",
        "description": "One of America's oldest roads, the Natchez Trace followed ancient Native American paths through the Old Southwest, linking the Mississippi River port of Natchez to Nashville, Tennessee. Flatboat men who floated goods downriver to Natchez walked this trace northward home, earning the nickname 'Kaintucks.'",
        "coordinates": [[-91.4032,31.5604],[-91.0000,32.0000],[-90.9000,32.2988],[-90.2000,32.7000],[-89.9711,34.2600],[-88.7037,34.5500],[-88.0000,34.9889],[-87.0000,35.1500],[-86.7816,36.1627]]
    },
    {
        "name": "Bozeman Trail",
        "years": "1863-1868",
        "description": "Blazed by John Bozeman in 1863 as a shortcut to the Montana goldfields, the Bozeman Trail cut directly through the Powder River Basin, prime hunting grounds of the Lakota and Cheyenne. Red Cloud's War (1866-1868) forced the U.S. Army to abandon its forts along the trail, making it the only conflict in which the government conceded defeat to Native Americans.",
        "coordinates": [[-104.5450,42.2125],[-104.5000,43.0000],[-106.4000,43.9000],[-106.5500,44.3000],[-106.9506,44.5244],[-107.5000,45.0000],[-107.9195,45.3170],[-108.5000,45.6000],[-110.7624,45.6796]]
    },
    {
        "name": "Old Spanish Trail",
        "years": "1829-1848",
        "description": "The Old Spanish Trail connected the Spanish colonial settlements of New Mexico with the missions of Alta California through the harsh Colorado Plateau and Mojave Desert. First fully traversed by Antonio Armijo in 1829-1830, it became a mule trade route carrying woolen blankets west and returning with horses and mules.",
        "coordinates": [[-105.9378,35.6870],[-106.5000,36.5000],[-107.8801,37.2753],[-109.5500,38.5500],[-110.0000,38.0000],[-111.0000,37.5000],[-113.0000,37.0000],[-114.0000,36.0000],[-115.1398,36.1699],[-117.0000,34.5000],[-118.2437,34.0522]]
    },
    {
        "name": "Gila Trail",
        "years": "1846-1850s",
        "description": "The Gila Trail followed the Gila River across the Sonoran Desert, providing the southernmost all-weather route to California during the Gold Rush era. Pioneered during the Mexican-American War by General Kearny's Army of the West, it later became a major route for thousands of Forty-Niners.",
        "coordinates": [[-106.4850,31.7619],[-108.0000,32.0000],[-109.5000,32.3000],[-110.9747,32.2226],[-112.0740,33.4484],[-113.5000,33.2000],[-114.6277,32.6927],[-117.1610,32.7153]]
    },
    {
        "name": "El Camino Real de Tierra Adentro",
        "years": "1598-1882",
        "description": "The Royal Road of the Interior Land, stretching nearly 1,800 miles from Mexico City to Santa Fe, was the lifeline of Spanish colonial New Mexico for nearly three centuries. Established by Juan de Oñate in 1598, it was one of the longest and oldest European trade routes in North America.",
        "coordinates": [[-106.4850,31.7619],[-106.6000,32.5000],[-107.2500,33.0000],[-107.2500,33.8500],[-106.6504,35.0844],[-106.4500,35.4500],[-105.9378,35.6870]]
    },
    {
        "name": "Wilderness Road / Boone's Trace",
        "years": "1775-1810",
        "description": "Blazed by Daniel Boone and a party of axemen for the Transylvania Company in 1775, the Wilderness Road opened the trans-Appalachian frontier to settlement. By 1800 it had carried an estimated 300,000 settlers through the Cumberland Gap into Kentucky and the Ohio Valley.",
        "coordinates": [[-82.5620,36.5484],[-83.6000,36.6000],[-83.6770,36.6017],[-84.0000,36.9000],[-84.2000,37.4000],[-84.2981,37.5678],[-84.5000,37.9500],[-84.4947,38.0523]]
    },
    {
        "name": "Great Wagon Road",
        "years": "1730s-1780s",
        "description": "The Great Wagon Road was the most heavily traveled road in colonial America, carrying German and Scots-Irish immigrants from Philadelphia southward through the Shenandoah Valley and into the Carolina backcountry. By the eve of the Revolution, it had carried over 100,000 settlers into the southern frontier.",
        "coordinates": [[-75.1652,39.9526],[-76.3055,40.0379],[-76.7275,39.9626],[-77.7199,39.6418],[-78.1633,39.1857],[-79.9420,37.2710],[-80.4139,37.2796],[-81.0000,36.5000],[-80.8431,35.2271],[-81.5000,34.0000],[-81.9748,33.4735]]
    },
    {
        "name": "Chisholm Trail",
        "years": "1867-1884",
        "description": "The most famous of the Texas cattle trails, the Chisholm Trail carried an estimated five million longhorns northward from Texas to the Kansas railheads between 1867 and 1884. Named for trader Jesse Chisholm who had blazed a wagon road through Indian Territory, it defined the era of the open-range cattle drive.",
        "coordinates": [[-98.4936,29.4241],[-98.0000,30.0000],[-97.7431,30.2672],[-97.5000,31.0000],[-97.1469,31.5493],[-97.0000,32.0000],[-97.3208,32.7254],[-97.5000,33.5000],[-97.9000,34.5000],[-98.3000,35.5000],[-98.3000,36.5000],[-97.0000,37.0000],[-97.2167,38.9517]]
    },
    {
        "name": "Goodnight-Loving Trail",
        "years": "1866-1889",
        "description": "Pioneered by Charles Goodnight and Oliver Loving in 1866, this trail blazed a new path westward through the Pecos River valley to supply beef to New Mexico forts and Colorado mining camps. Loving was fatally wounded by Comanche warriors on a scouting trip in 1867, and the trail's story inspired Larry McMurtry's Lonesome Dove.",
        "coordinates": [[-100.4359,31.4638],[-101.4000,31.8500],[-102.0000,31.4200],[-103.5000,31.4500],[-104.4244,31.7587],[-104.4000,32.5000],[-104.5150,34.1700],[-104.6000,35.0000],[-104.6800,36.5000],[-104.5000,37.0000],[-104.9845,39.7392],[-104.9847,41.1400]]
    },
    {
        "name": "Western Trail / Dodge City Trail",
        "years": "1874-1893",
        "description": "Established in 1874 when Abilene's cattle era ended and Dodge City rose as the new cow capital, the Western Trail ultimately carried more cattle northward than even the famous Chisholm Trail. At its peak in the early 1880s, the trail saw hundreds of thousands of longhorns pass through Dodge City annually.",
        "coordinates": [[-99.0740,29.7274],[-99.1403,30.0474],[-100.4359,31.4638],[-99.7167,32.4487],[-98.7167,33.0000],[-99.5000,34.0000],[-100.5000,35.0000],[-100.0000,36.0000],[-99.7667,37.7528],[-99.0000,38.5000],[-100.0000,39.5000],[-101.7011,40.7267]]
    },
    {
        "name": "Shawnee Trail",
        "years": "1840s-1860s",
        "description": "The earliest of the great Texas cattle trails, the Shawnee Trail (also called the Texas Road or Sedalia Trail) carried longhorns northeastward to Missouri markets before the Civil War and resumed briefly afterward. It was eventually abandoned due to resistance from Missouri and Kansas farmers who feared Texas fever decimating their livestock.",
        "coordinates": [[-95.3698,29.7604],[-96.0000,30.5000],[-96.7970,32.7767],[-96.5000,33.5000],[-95.5000,34.5000],[-94.9000,35.5000],[-94.5000,36.0000],[-94.9785,37.0282],[-94.4000,37.5000],[-93.2000,38.5000],[-93.2283,38.7048]]
    },
    {
        "name": "Smoky Hill Trail",
        "years": "1859-1870",
        "description": "The Smoky Hill Trail was the most direct route from the Missouri River to Denver, following the Smoky Hill River across Kansas. Despite its shorter distance, it was notorious for lack of water and food in western Kansas, earning it the name 'Starvation Trail' before military posts were established along the route.",
        "coordinates": [[-94.5784,39.0997],[-96.8000,39.1000],[-96.5000,38.5000],[-97.5000,38.5000],[-98.0000,38.5000],[-99.0000,38.5000],[-100.0000,38.5000],[-101.0000,38.5000],[-102.0000,38.5000],[-103.0000,38.8000],[-104.9847,39.7392]]
    },
    {
        "name": "Lander Road / Lander Cutoff",
        "years": "1858-1869",
        "description": "Surveyed by Frederick Lander and constructed with federal funds in 1858, the Lander Road provided an improved northern cutoff to the Oregon Trail that bypassed the barren desert around Fort Bridger. It was the first federally funded road improvement project west of the Mississippi River.",
        "coordinates": [[-108.8600,42.5000],[-110.0000,42.7000],[-111.0000,42.5000],[-112.0000,42.5000],[-112.4455,42.8713]]
    },
    {
        "name": "Mullan Road",
        "years": "1860-1862",
        "description": "Built by Army Lieutenant John Mullan between 1859 and 1862, the Mullan Road was a 624-mile military wagon road connecting the navigable waters of the Missouri River at Fort Benton to the Columbia River system at Walla Walla. It opened the northern Rocky Mountain region to settlement and became a major immigration route.",
        "coordinates": [[-110.6699,47.8211],[-112.0269,46.5958],[-112.3000,46.0000],[-113.9966,46.8721],[-114.0000,47.0000],[-116.5000,47.6788],[-117.0000,47.5000],[-118.3430,46.0646]]
    },
    {
        "name": "Nez Perce Trail - Flight of 1877",
        "years": "1877",
        "description": "In the summer of 1877, Chief Joseph and approximately 800 Nez Perce men, women, and children fled 1,170 miles across Idaho, Wyoming, and Montana to escape forced relocation to a reservation. They were stopped just 40 miles from the Canadian border at the Battle of Bear Paw, where Chief Joseph delivered his famous surrender speech.",
        "coordinates": [[-117.2000,45.5000],[-116.0000,46.0000],[-114.5847,46.5442],[-113.5000,46.2000],[-113.3000,45.6500],[-112.5000,45.2000],[-111.0000,44.5000],[-109.5000,45.0000],[-109.7000,48.5000]]
    },
    {
        "name": "Cherokee Trail",
        "years": "1849-1860s",
        "description": "The Cherokee Trail was blazed in 1849 by a party of Cherokee men from Indian Territory seeking a gold rush route to California via the southern Rockies. It became an important alternative route connecting the southern states to Utah and California, following the Arkansas River and crossing the Rockies at Raton Pass.",
        "coordinates": [[-94.3985,35.3859],[-95.0000,36.0000],[-95.5000,36.7000],[-96.0000,37.0000],[-97.0000,37.5000],[-99.0000,37.5000],[-101.0000,37.5000],[-103.0000,37.3000],[-104.5000,37.2000],[-104.5000,37.0000],[-106.3489,39.5501],[-110.3874,41.3166],[-111.3874,40.7608]]
    },
    {
        "name": "Cooke's Wagon Road",
        "years": "1846-1847",
        "description": "Blazed by Mormon Battalion commander Philip St. George Cooke in 1846-1847, Cooke's Wagon Road was the first wagon route from New Mexico to California. The 2,000-mile march of the Mormon Battalion proved the southern route was viable for wagon travel and established an important military road.",
        "coordinates": [[-105.9378,35.6870],[-106.8000,33.5000],[-107.8000,33.0000],[-109.0000,32.0000],[-110.9747,32.2226],[-112.0000,32.5000],[-113.5000,32.5000],[-114.6277,32.6927],[-117.1610,32.7153]]
    },
    {
        "name": "Applegate Trail",
        "years": "1846",
        "description": "Pioneered in 1846 by brothers Jesse and Lindsay Applegate as a supposedly safer southern alternative to the dangerous Columbia River section of the Oregon Trail, the Applegate Trail entered Oregon through the Klamath Basin. Despite the brothers' good intentions, the route proved extremely difficult and desert crossings caused immense suffering.",
        "coordinates": [[-112.4455,42.8713],[-115.7271,42.6000],[-117.0000,41.5000],[-118.5000,41.5000],[-120.3000,41.9800],[-121.5000,42.2000],[-122.5000,43.2000],[-123.0867,44.0521]]
    },
    {
        "name": "Barlow Road",
        "years": "1845",
        "description": "Opened by Samuel Barlow in 1846 as a toll road over the southern slopes of Mount Hood, the Barlow Road provided the first all-land route from The Dalles to the Willamette Valley. Before its construction, emigrants faced the dangerous Columbia River rapids or expensive river passage to reach Oregon City.",
        "coordinates": [[-121.1789,45.6052],[-121.5000,45.5000],[-121.7000,45.3500],[-121.9000,45.3000],[-122.1000,45.4000],[-122.6765,45.5231]]
    },
    {
        "name": "Hastings Cutoff",
        "years": "1846",
        "description": "Promoted by Lansford Hastings as a shortcut to California, the Hastings Cutoff crossed the treacherous Great Salt Lake Desert and actually proved longer and more dangerous than the established route. The Donner-Reed Party's decision to take this route in 1846 contributed directly to their catastrophic entrapment in the Sierra Nevada.",
        "coordinates": [[-110.3874,41.3166],[-112.0000,40.8000],[-113.5000,40.5000],[-115.0000,40.5000],[-116.0000,40.5000],[-116.5000,40.5000],[-117.0000,40.7000]]
    },
    {
        "name": "Beckwourth Trail",
        "years": "1851",
        "description": "Discovered by mountain man and former slave Jim Beckwourth in 1851, the Beckwourth Trail crossed the Sierra Nevada at what is now Beckwourth Pass, the lowest pass through the northern Sierra. Beckwourth actively recruited emigrants at the Humboldt River to use his route, which he had promoted to a nearby town for commercial benefit.",
        "coordinates": [[-119.8138,39.5296],[-120.3000,39.8000],[-120.5000,39.9000],[-120.9000,39.7000],[-121.4944,38.5816]]
    },
    {
        "name": "Carson Route",
        "years": "1848",
        "description": "The Carson Route via Carson Pass was identified by Kit Carson during Frémont's 1844 expedition and became one of the primary Sierra Nevada crossings for California-bound emigrants. The route entered the Sierra at a more southerly point than Donner Pass and funneled emigrants toward the American River drainage and Sutter's Fort.",
        "coordinates": [[-119.8138,39.5296],[-120.1000,38.9000],[-120.4000,38.7000],[-120.7000,38.5000],[-121.4944,38.5816]]
    },
    {
        "name": "Donner Pass Route",
        "years": "1844",
        "description": "The Donner Pass crossing of the Sierra Nevada was first used by the Stephens-Townsend-Murphy Party in 1844, who successfully crossed the mountains just before winter closed in. Two years later, the Donner-Reed Party became stranded here, and the resulting tragedy of cannibalism and death became the most harrowing story of overland emigration.",
        "coordinates": [[-119.8000,39.3000],[-120.1000,39.3500],[-120.3100,39.3200],[-120.5000,39.2000],[-120.8000,38.9500],[-121.4944,38.5816]]
    },
    {
        "name": "King's Highway / El Camino Real de los Tejas",
        "years": "1690s-1790s",
        "description": "El Camino Real de los Tejas, the Royal Road of the Tejas, linked the Spanish settlements of Texas with French Louisiana along an ancient Native American path. Established in the 1690s to counter French expansion into Texas, it connected missions, presidios, and towns across the Texas interior for over a century.",
        "coordinates": [[-98.4936,29.4241],[-98.0000,29.7000],[-97.5000,30.0000],[-96.7970,30.4000],[-96.0000,30.9000],[-95.0000,31.1000],[-94.7256,31.6035],[-94.0000,31.7500],[-93.5000,31.7500],[-93.0860,31.7543]]
    },
    {
        "name": "Kearny Trail",
        "years": "1846",
        "description": "General Stephen Kearny led his Army of the West along this route in 1846 to conquer New Mexico during the Mexican-American War, following much of the Santa Fe Trail. The army's swift capture of Santa Fe without firing a shot marked the beginning of American rule over the Southwest.",
        "coordinates": [[-94.9100,39.3600],[-96.0000,39.0000],[-97.0000,38.5000],[-98.0000,38.0000],[-99.0000,37.5000],[-100.0000,37.5000],[-101.0000,37.5000],[-102.5000,37.9800],[-103.5500,37.4900],[-104.5000,36.9100],[-105.9378,35.6870]]
    },
    {
        "name": "Emigrant Trail / Humboldt Route",
        "years": "1840s-1860s",
        "description": "The Humboldt Route followed the Humboldt River across the Nevada desert, providing the critical water and forage corridor for westbound California emigrants. The Humboldt Sink at the river's terminus presented the final major challenge before the Sierra Nevada, as emigrants faced a brutal 40-mile desert crossing.",
        "coordinates": [[-112.4455,42.8713],[-114.5000,42.0000],[-115.7271,42.6000],[-116.0000,42.0000],[-116.5000,41.5000],[-117.0000,41.0000],[-117.5000,40.5000],[-118.0000,40.0000],[-118.5000,39.5000],[-118.7000,39.3000]]
    },
    {
        "name": "Zane's Trace",
        "years": "1796-1800s",
        "description": "Surveyed by Ebenezer Zane under a congressional land grant in 1796-1797, Zane's Trace was the first road through the Northwest Territory, cutting diagonally across Ohio from Wheeling to Limestone (Maysville), Kentucky. The three ferry crossings at Zanesville, Lancaster, and Chillicothe each grew into important Ohio towns.",
        "coordinates": [[-80.7209,40.0640],[-81.5000,40.0000],[-81.9946,39.9401],[-83.0000,39.5000],[-83.7500,38.9000],[-84.3100,38.9000],[-84.5120,39.1031]]
    },
    {
        "name": "National Road / Cumberland Road",
        "years": "1811-1830s",
        "description": "The National Road was the first federally funded interstate highway in the United States, authorized by Congress in 1806 and constructed from Cumberland, Maryland westward to Vandalia, Illinois by 1839. It served as the primary artery for westward migration before the railroad era, handling enormous traffic in goods, livestock, and settlers.",
        "coordinates": [[-78.7625,39.6528],[-79.5000,39.7000],[-80.7209,40.0640],[-81.5000,40.2000],[-82.0000,40.0000],[-82.9988,39.9612],[-83.5000,39.8000],[-84.5120,39.7700],[-85.0000,39.7700],[-85.5000,39.7700],[-86.1581,39.7684],[-87.0000,39.5000],[-89.1440,38.9606]]
    },
    {
        "name": "Trapper's Trail / Cache Valley Trail",
        "years": "1820s-1840s",
        "description": "The Trapper's Trail was the informal network of paths used by Rocky Mountain fur trappers to connect the trading hub of Taos, New Mexico with the annual mountain man rendezvous sites and eventually South Pass. It preceded the major emigrant trails and much of its course was later incorporated into the Overland Trail system.",
        "coordinates": [[-105.5731,36.4072],[-105.0000,37.0000],[-104.9845,39.7392],[-105.0000,40.5000],[-106.3489,39.5501],[-107.0000,41.0000],[-108.8600,42.5000]]
    },
    {
        "name": "Bozeman Road - Northern Extension",
        "years": "1864-1866",
        "description": "The northern extension of the Bozeman Trail connected the gold mining center of Virginia City, Montana with the Missouri River steamboat terminus at Fort Benton, providing a supply route for the booming mining camps of southwestern Montana. This segment saw heavy freight wagon traffic during the height of the Montana gold rush.",
        "coordinates": [[-110.7624,45.6796],[-111.5000,46.0000],[-111.9000,46.5000],[-112.0269,46.5958],[-110.6699,47.8211]]
    },
    {
        "name": "Cimarron Cutoff / Dry Route",
        "years": "1822-1880",
        "description": "The Cimarron Cutoff shaved 100 miles off the Mountain Branch of the Santa Fe Trail by cutting across the Cimarron Desert, but the waterless stretch between the Arkansas and Cimarron Rivers made it extremely dangerous. Despite frequent attacks by Comanche and Kiowa warriors, most commercial caravans preferred this shorter route to avoid the mountains.",
        "coordinates": [[-96.4892,38.6617],[-97.5000,38.3000],[-98.5000,38.0000],[-99.7667,37.7528],[-100.5000,37.5000],[-101.3000,37.0000],[-102.5000,36.5000],[-103.5000,36.5000],[-104.5000,36.0000],[-105.9378,35.6870]]
    },
    {
        "name": "El Camino del Diablo",
        "years": "1699-1849",
        "description": "El Camino del Diablo (The Devil's Highway) was one of the most dangerous trails in North America, traversing 250 miles of the Sonoran Desert with limited water sources. First used by Father Kino in the 1690s to connect his missions, it later became a desperate shortcut for California-bound forty-niners, hundreds of whom perished from thirst.",
        "coordinates": [[-111.7000,30.5000],[-111.0000,30.7000],[-113.0000,31.5000],[-114.0000,32.0000],[-114.6277,32.6927],[-117.1610,32.7153]]
    },
    {
        "name": "Butterfield Trail Connecting Segment",
        "years": "1858-1861",
        "description": "The eastern segment of the Butterfield Overland Mail route connected Memphis and St. Louis to Fort Smith, Arkansas before crossing Indian Territory into Texas. This section passed through the Cherokee and Choctaw nations and marked the eastern approach to the great southwestern overland route.",
        "coordinates": [[-90.0490,35.1495],[-90.5000,35.5000],[-91.0000,35.5000],[-92.0000,35.3000],[-94.3985,35.3859],[-95.0000,35.6000],[-96.0000,35.7000],[-96.7970,35.9000],[-96.8000,36.1000],[-97.0000,36.1000],[-97.5000,36.0000],[-96.5884,33.6357]]
    },
]

LANDMARKS = [
    # Oregon/California/Mormon Trail
    {"name": "Independence, MO", "latitude": 39.0911, "longitude": -94.4155, "trails": ["Oregon Trail", "California Trail", "Santa Fe Trail", "Pony Express Route"], "confidence": 0.9, "description": "The 'Queen City of the Trails,' Independence was the primary jumping-off point for the Oregon, California, and Santa Fe Trails. Emigrants from the eastern states gathered here each spring to outfit for the long journey west."},
    {"name": "Westport, MO", "latitude": 39.0361, "longitude": -94.5786, "trails": ["Oregon Trail", "California Trail"], "confidence": 0.9, "description": "Located just west of present-day Kansas City, Westport was a rival jumping-off point to Independence and a major outfitting center for overland emigrants. Its early prominence as a fur trade depot made it a natural staging ground for westward migration."},
    {"name": "Council Grove, KS", "latitude": 38.6617, "longitude": -96.4892, "trails": ["Santa Fe Trail"], "confidence": 0.9, "description": "The last major supply point on the Santa Fe Trail before the open plains, Council Grove was named for a 1825 treaty council held under a large oak tree. Wagon trains typically reorganized here into defensive caravans before venturing into potentially hostile territory."},
    {"name": "Fort Kearny, NE", "latitude": 40.6519, "longitude": -99.0050, "trails": ["Oregon Trail", "California Trail", "Mormon Trail", "Pony Express Route"], "confidence": 0.9, "description": "Established in 1848 to protect emigrants on the Platte River Road, Fort Kearny was the first military post encountered on the Oregon Trail. It served as a critical supply and repair point for thousands of overland emigrants and Pony Express riders."},
    {"name": "Chimney Rock, NE", "latitude": 41.7061, "longitude": -103.3477, "trails": ["Oregon Trail", "California Trail", "Pony Express Route"], "confidence": 0.95, "description": "Rising 325 feet above the North Platte River valley, Chimney Rock was the most famous and often-described landmark on the Oregon Trail. Emigrants mentioned it in their diaries more than any other feature, and its distinctive spire signaled that the emigrants were entering the Rocky Mountain region."},
    {"name": "Scotts Bluff, NE", "latitude": 41.8344, "longitude": -103.7129, "trails": ["Oregon Trail", "California Trail", "Pony Express Route"], "confidence": 0.9, "description": "Scotts Bluff was a dramatic sandstone promontory that forced the Oregon Trail through the narrow Mitchell Pass. Named for fur trader Hiram Scott who died near its base around 1828, it was a major visual landmark and trail milestone."},
    {"name": "Fort Laramie, WY", "latitude": 42.2097, "longitude": -104.5491, "trails": ["Oregon Trail", "California Trail", "Mormon Trail", "Pony Express Route", "Bozeman Trail"], "confidence": 0.95, "description": "Originally a fur trading post known as Fort William, Fort Laramie became the most important military installation on the central overland route. Emigrants rested, repaired equipment, and sent last letters home from here before venturing into the more challenging terrain ahead."},
    {"name": "Register Cliff, WY", "latitude": 42.1264, "longitude": -104.5155, "trails": ["Oregon Trail", "California Trail"], "confidence": 0.85, "description": "The soft sandstone of Register Cliff bears the carved signatures of thousands of Oregon and California Trail emigrants who passed between 1840 and 1870. Hundreds of names, dates, and destinations are still legible, making it one of the most tangible remnants of overland emigration."},
    {"name": "Independence Rock, WY", "latitude": 42.4942, "longitude": -107.7251, "trails": ["Oregon Trail", "California Trail", "Mormon Trail", "Pony Express Route"], "confidence": 0.95, "description": "Called the 'Register of the Desert' by Father Pierre-Jean De Smet, Independence Rock bears the inscribed names of thousands of emigrants who scratched their marks into its granite surface. Emigrants needed to reach this landmark by July 4th to have a reasonable chance of crossing the Sierra Nevada before winter."},
    {"name": "South Pass, WY", "latitude": 42.6361, "longitude": -108.9417, "trails": ["Oregon Trail", "California Trail", "Mormon Trail", "Pony Express Route", "Lander Road / Lander Cutoff"], "confidence": 0.95, "description": "The broad, gentle crossing of the Continental Divide at South Pass made overland wagon travel to the Pacific possible, and was perhaps the single most important geographic feature in the history of westward expansion. Emigrants crossing here were technically halfway to Oregon City, though the most difficult terrain still lay ahead."},
    {"name": "Fort Bridger, WY", "latitude": 41.3166, "longitude": -110.3874, "trails": ["Oregon Trail", "California Trail", "Mormon Trail", "Pony Express Route", "Cherokee Trail", "Hastings Cutoff"], "confidence": 0.9, "description": "Established by mountain man Jim Bridger in 1843 as a trading post for Oregon-bound emigrants, Fort Bridger became a key decision point where travelers chose between the established trail and shortcuts like the Hastings Cutoff. The Mormons purchased it in 1855 and it later became a U.S. Army post."},
    {"name": "Fort Hall, ID", "latitude": 43.0282, "longitude": -112.4095, "trails": ["Oregon Trail", "California Trail", "Pony Express Route", "Lander Road / Lander Cutoff", "Emigrant Trail / Humboldt Route"], "confidence": 0.9, "description": "Founded by Nathaniel Wyeth in 1834 and later sold to the Hudson's Bay Company, Fort Hall was the parting of the ways where California-bound emigrants left the Oregon Trail and headed southwest. The fort's factor, Richard Grant, reportedly discouraged emigration to California to maintain the fur trade."},
    {"name": "Three Island Crossing, ID", "latitude": 43.0000, "longitude": -115.7000, "trails": ["Oregon Trail"], "confidence": 0.8, "description": "The Three Island Crossing of the Snake River was one of the most dangerous river crossings on the Oregon Trail, where emigrants could either ford the river on stepping-stone islands or continue on the difficult south bank route. Many wagons overturned and some emigrants drowned at this crossing."},
    {"name": "Fort Boise, ID", "latitude": 43.6500, "longitude": -116.2000, "trails": ["Oregon Trail"], "confidence": 0.85, "description": "Hudson's Bay Company's Fort Boise provided the last resupply opportunity for Oregon-bound emigrants before the Blue Mountains. Like Fort Hall, it was operated by the British company that initially resisted American emigration but provided essential assistance to travelers in need."},
    {"name": "The Dalles, OR", "latitude": 45.5946, "longitude": -121.1789, "trails": ["Oregon Trail", "Barlow Road"], "confidence": 0.9, "description": "The Dalles was the practical end of overland travel on the Oregon Trail, where emigrants had to either raft their wagons down the treacherous Columbia River rapids or pay toll on the newly-opened Barlow Road to reach the Willamette Valley. The name comes from the French word for flagstones describing the basalt rock formations."},
    {"name": "Oregon City, OR", "latitude": 45.3573, "longitude": -122.6065, "trails": ["Oregon Trail", "Barlow Road"], "confidence": 0.9, "description": "Oregon City was the official terminus of the Oregon Trail, the first incorporated American city west of the Rocky Mountains, and the capital of the Oregon Territory. Emigrants who survived the arduous 2,000-mile journey arrived here to begin their new lives in the Pacific Northwest."},
    {"name": "City of Rocks, ID", "latitude": 42.0706, "longitude": -113.7150, "trails": ["California Trail"], "confidence": 0.85, "description": "This dramatic formation of granite spires and boulders in southern Idaho was a famous landmark on the California Trail where emigrants carved their names in axle grease on the rocks. The parting of the Oregon and California trails officially occurred nearby at Raft River junction."},
    {"name": "Humboldt Sink, NV", "latitude": 39.8000, "longitude": -118.6500, "trails": ["California Trail", "Emigrant Trail / Humboldt Route"], "confidence": 0.8, "description": "Where the Humboldt River disappeared into the desert, emigrants faced the dread 'Forty Mile Desert' crossing to reach the Truckee or Carson Rivers and the Sierra Nevada beyond. Dead animals, abandoned wagons, and desperate emigrants littered this stretch, making it one of the most dreaded sections of the California Trail."},
    {"name": "Carson Sink, NV", "latitude": 39.7000, "longitude": -118.7500, "trails": ["California Trail"], "confidence": 0.8, "description": "The Carson Sink marked the end of the Carson River branch of the California Trail and the beginning of the final desert crossing before the Sierra Nevada. Emigrants typically rested here before attempting the brutal 50-mile desert stretch to reach the mountains."},
    {"name": "Donner Pass, CA", "latitude": 39.3200, "longitude": -120.3100, "trails": ["California Trail", "Donner Pass Route"], "confidence": 0.9, "description": "The Truckee Pass, later renamed Donner Pass after the tragic 1846-47 disaster, was the primary Sierra Nevada crossing for California-bound emigrants from the north. The stranding of the Donner-Reed Party here, with 87 people snowbound for four months and 41 perishing, became the most dramatic tragedy of westward migration."},
    {"name": "Sutter's Fort, CA", "latitude": 38.5751, "longitude": -121.4990, "trails": ["California Trail", "Oregon Trail"], "confidence": 0.9, "description": "John Sutter's agricultural and trading empire in the Sacramento Valley was the destination of most California-bound emigrants, providing food, employment, and a base to begin new lives. It was near Sutter's Mill that James Marshall discovered gold in January 1848, triggering the California Gold Rush."},
    {"name": "Nauvoo, IL", "latitude": 40.5500, "longitude": -91.3810, "trails": ["Mormon Trail"], "confidence": 0.9, "description": "The 'City Beautiful' on the Mississippi River was the thriving center of the Latter-day Saint community until anti-Mormon violence forced the Exodus of 1846. At its height Nauvoo rivaled Chicago in population, and its abandonment under duress marks one of the greatest forced migrations in American history."},
    {"name": "Winter Quarters, NE", "latitude": 41.3000, "longitude": -96.0500, "trails": ["Mormon Trail"], "confidence": 0.85, "description": "Established on the banks of the Missouri River in 1846-1847 as a temporary refuge for fleeing Latter-day Saints, Winter Quarters became a sprawling community of 3,500 people. The bitter winter of 1846-47 claimed hundreds of lives, and a moving pioneer cemetery near the site commemorates those who died there."},
    {"name": "Salt Lake City, UT", "latitude": 40.7608, "longitude": -111.8910, "trails": ["Mormon Trail", "Pony Express Route", "Cherokee Trail"], "confidence": 0.95, "description": "Founded by Brigham Young and the Mormon pioneers in July 1847 in the valley of the Great Salt Lake, Salt Lake City became the spiritual and commercial hub of the Great Basin. The city grew rapidly into a major waystation for California-bound emigrants and the center of Mormon civilization."},
    # Santa Fe Trail
    {"name": "Arrow Rock, MO", "latitude": 39.0747, "longitude": -92.9482, "trails": ["Santa Fe Trail"], "confidence": 0.85, "description": "Arrow Rock was an important early waypoint on the Santa Fe Trail, known for its salt lick and river crossing used by Native Americans long before European contact. The town that grew here became home to several prominent Missouri politicians and artists."},
    {"name": "Fort Osage, MO", "latitude": 39.1750, "longitude": -94.0167, "trails": ["Santa Fe Trail"], "confidence": 0.85, "description": "Built in 1808 under the direction of William Clark, Fort Osage was the westernmost U.S. outpost for nearly two decades and the location of the government's first factory trading post with Native Americans. It served as an early waypoint for Santa Fe-bound traders."},
    {"name": "Fort Larned, KS", "latitude": 38.1850, "longitude": -99.2186, "trails": ["Santa Fe Trail"], "confidence": 0.9, "description": "Established in 1859 to protect Santa Fe Trail travelers from Kiowa and Cheyenne raids, Fort Larned was one of the most active military posts on the central plains during the Indian Wars of the 1860s. The well-preserved fort is now a National Historic Site."},
    {"name": "Bent's Old Fort, CO", "latitude": 38.0394, "longitude": -103.4250, "trails": ["Santa Fe Trail", "Trapper's Trail / Cache Valley Trail"], "confidence": 0.9, "description": "Built by brothers Charles and William Bent around 1833, Bent's Old Fort was the premier trading post on the southern plains, strategically located on the Santa Fe Trail's Mountain Branch. The adobe fort served trappers, Cheyenne and Arapaho traders, and emigrants until it was mysteriously destroyed in 1849."},
    {"name": "Raton Pass, NM", "latitude": 37.0500, "longitude": -104.5000, "trails": ["Santa Fe Trail", "Goodnight-Loving Trail", "Cherokee Trail"], "confidence": 0.9, "description": "The crossing of the Sangre de Cristo Mountains at Raton Pass presented the most challenging terrain obstacle on the Mountain Branch of the Santa Fe Trail. Richens Lacy 'Uncle Dick' Wootton built a toll road over the pass in 1865, which the Atchison, Topeka and Santa Fe Railway later acquired."},
    {"name": "Cimarron Crossing, KS", "latitude": 37.7528, "longitude": -100.3500, "trails": ["Santa Fe Trail", "Cimarron Cutoff / Dry Route"], "confidence": 0.8, "description": "The Cimarron Crossing of the Arkansas River marked the divergence of the Santa Fe Trail's Mountain and Cimarron (Dry) Routes. Caravans choosing the shorter Cimarron Cutoff faced the waterless stretch of the Jornada to reach the safety of the Cimarron River."},
    {"name": "Fort Union, NM", "latitude": 35.9167, "longitude": -104.9500, "trails": ["Santa Fe Trail"], "confidence": 0.9, "description": "Established in 1851 as the largest military installation in the Southwest, Fort Union protected the Santa Fe Trail's southern reaches and served as the principal supply depot for military operations in New Mexico and the surrounding territories. Deep wagon ruts from the trail are still visible at the site."},
    {"name": "Santa Fe, NM", "latitude": 35.6870, "longitude": -105.9378, "trails": ["Santa Fe Trail", "El Camino Real de Tierra Adentro", "Old Spanish Trail", "Kearny Trail"], "confidence": 0.95, "description": "Founded in 1610 as the capital of the Kingdom of New Mexico, Santa Fe was one of North America's oldest continuously inhabited cities and the terminus of multiple historic trails. Its famous Palace of the Governors on the plaza witnessed the arrival of Kearny's conquering army in 1846."},
    # Pony Express
    {"name": "St. Joseph, MO", "latitude": 39.7675, "longitude": -94.8467, "trails": ["Pony Express Route"], "confidence": 0.9, "description": "The eastern terminus of the Pony Express, St. Joseph was a booming frontier city where the first rider, Johnny Fry, dashed westward on April 3, 1860 to initiate the service. The Pikes Peak Stables where the Pony Express operated are now preserved as a museum."},
    {"name": "Gothenburg Station, NE", "latitude": 40.9271, "longitude": -100.1606, "trails": ["Pony Express Route"], "confidence": 0.85, "description": "The Gothenburg Pony Express station was one of the relay stations where riders exchanged horses and briefly rested during the grueling overland run. The original station building, relocated to a park in Gothenburg, is one of the few surviving authentic Pony Express stations."},
    {"name": "Julesburg, CO", "latitude": 40.9875, "longitude": -102.2583, "trails": ["Pony Express Route", "Smoky Hill Trail"], "confidence": 0.85, "description": "Fort Sedgwick at Julesburg was an important Pony Express station and later a notorious frontier town that was twice destroyed by Cheyenne and Sioux warriors in the winter of 1865. It sat at the crossroads of several major overland routes."},
    {"name": "Fort Caspar, WY", "latitude": 42.8500, "longitude": -106.3000, "trails": ["Pony Express Route", "Oregon Trail"], "confidence": 0.85, "description": "Originally a Pony Express and Overland Stage station near a Mormon ferry crossing of the North Platte River, Fort Caspar was attacked by Cheyenne, Sioux, and Arapaho warriors in 1865 during Red Cloud's war. Lieutenant Caspar Collins was killed in the engagement that gave the fort its name."},
    {"name": "Camp Floyd, UT", "latitude": 40.3000, "longitude": -112.1000, "trails": ["Pony Express Route"], "confidence": 0.8, "description": "Established during the Utah War of 1857-58, Camp Floyd was briefly the largest military post in the United States with 3,500 troops. It served as an important Pony Express relay station and its auction of military equipment at the outbreak of the Civil War provided settlers with inexpensive goods."},
    {"name": "Ruby Valley Station, NV", "latitude": 40.5000, "longitude": -115.5000, "trails": ["Pony Express Route"], "confidence": 0.8, "description": "Ruby Valley Station was one of the home stations on the Nevada stretch of the Pony Express where riders could rest and eat a hot meal. The Ruby Mountains provided a dramatic backdrop and the valley offered water and forage in the otherwise harsh Great Basin landscape."},
    {"name": "Friday's Station, NV", "latitude": 38.9000, "longitude": -119.9500, "trails": ["Pony Express Route"], "confidence": 0.8, "description": "Friday's Station near Lake Tahoe was the last Nevada relay station on the Pony Express route before riders ascended the Sierra Nevada into California. Young rider Bob Haslam covered the incredible distance from Friday's Station to Smith Creek and back, nearly 380 miles, when his relief rider refused to ride during the Pyramid Lake War."},
    # Natchez Trace
    {"name": "Natchez, MS", "latitude": 31.5604, "longitude": -91.4032, "trails": ["Natchez Trace"], "confidence": 0.9, "description": "The oldest city on the Mississippi River and southern terminus of the Natchez Trace, Natchez was a major cotton port and one of the wealthiest cities in antebellum America. Under-the-Hill, its notorious riverside district, catered to the boatmen who walked the Trace northward after selling their goods."},
    {"name": "Mount Locust Inn, MS", "latitude": 31.7000, "longitude": -91.3500, "trails": ["Natchez Trace"], "confidence": 0.85, "description": "Mount Locust was one of the earliest stands (inns) on the Natchez Trace, established around 1780 and used continuously by travelers on the Trace for decades. The restored plantation house is one of the few surviving stands and is maintained by the National Park Service."},
    {"name": "Port Gibson, MS", "latitude": 31.9553, "longitude": -90.9843, "trails": ["Natchez Trace"], "confidence": 0.85, "description": "Port Gibson sat near the Natchez Trace along the southwestern Mississippi bluffs and was spared destruction in the Civil War because General Grant declared it 'too beautiful to burn.' Its ornate antebellum churches and mansions reflect the prosperity of the cotton era."},
    {"name": "French Camp, MS", "latitude": 33.3000, "longitude": -89.4000, "trails": ["Natchez Trace"], "confidence": 0.8, "description": "French Camp was named for Louis LeFleur, a French-Canadian trader who established a stand here in the early 1800s. It was a major rest stop on the Natchez Trace and later the site of a Choctaw school established by missionaries."},
    {"name": "Tupelo, MS", "latitude": 34.2576, "longitude": -88.7037, "trails": ["Natchez Trace"], "confidence": 0.9, "description": "Near the site of the Chickasaw town of Ackia where the French were defeated in 1736, Tupelo sits along the Natchez Trace in northern Mississippi. The town later gained fame as the birthplace of Elvis Presley."},
    {"name": "Colbert's Ferry, TN", "latitude": 35.0000, "longitude": -87.5000, "trails": ["Natchez Trace"], "confidence": 0.8, "description": "Operated by George Colbert, a Chickasaw chief of Scottish descent, Colbert's Ferry was a profitable business on the Tennessee River crossing of the Natchez Trace. Colbert reportedly charged Andrew Jackson an exorbitant toll to cross with his army after the Battle of New Orleans."},
    {"name": "Nashville, TN", "latitude": 36.1627, "longitude": -86.7816, "trails": ["Natchez Trace"], "confidence": 0.9, "description": "The northern terminus of the Natchez Trace, Nashville was the destination for most of the flatboatmen who walked north from Natchez after selling their goods. Founded in 1779 as Fort Nashborough, it grew rapidly as the gateway to the western frontier."},
    # Bozeman Trail
    {"name": "Fort Reno, WY", "latitude": 43.7000, "longitude": -106.9000, "trails": ["Bozeman Trail"], "confidence": 0.8, "description": "The first of three forts built along the Bozeman Trail to protect miners and settlers from Lakota and Cheyenne resistance, Fort Reno was frequently besieged and was among the posts abandoned after Red Cloud's War. Its garrison experienced near-constant harassment throughout 1866-1867."},
    {"name": "Fort Phil Kearny, WY", "latitude": 44.5244, "longitude": -106.9506, "trails": ["Bozeman Trail"], "confidence": 0.85, "description": "The main fort along the Bozeman Trail was the site of the Fetterman Fight in December 1866, when Lt. Col. Fetterman disobeyed orders and led 80 soldiers to their deaths in the worst U.S. Army defeat on the northern plains prior to Little Bighorn. The fort was burned to the ground by victorious warriors immediately after its abandonment in 1868."},
    {"name": "Fort C.F. Smith, MT", "latitude": 45.3170, "longitude": -107.9195, "trails": ["Bozeman Trail"], "confidence": 0.8, "description": "The northernmost fort on the Bozeman Trail, Fort C.F. Smith in the Big Horn Valley was the scene of the Hayfield Fight in August 1867. The fort was also burned upon abandonment and Red Cloud, reviewing his successful campaign, said it was the only war in which a Native American chief won."},
    {"name": "Virginia City, MT", "latitude": 45.2961, "longitude": -111.9475, "trails": ["Bozeman Trail"], "confidence": 0.9, "description": "The gold rush town of Virginia City was the primary destination for travelers on the Bozeman Trail, booming to a population of 10,000 after gold was discovered in Alder Gulch in 1863. It served as the territorial capital of Montana from 1865 to 1875 and preserved many of its original buildings."},
    # Wilderness Road
    {"name": "Cumberland Gap, KY", "latitude": 36.6017, "longitude": -83.6770, "trails": ["Wilderness Road / Boone's Trace"], "confidence": 0.95, "description": "The Cumberland Gap was the great natural portal through the Appalachian Mountains, used by Native Americans, long hunters, and then the flood of settlers who followed Daniel Boone into Kentucky. Before Boone's Trace was cut, the gap had already been used for centuries as a natural crossing in the Cumberland Mountains."},
    {"name": "Boonesborough, KY", "latitude": 37.9000, "longitude": -84.2300, "trails": ["Wilderness Road / Boone's Trace"], "confidence": 0.9, "description": "Established by Daniel Boone and the Transylvania Company in 1775, Fort Boonesborough was the first Anglo-American settlement in Kentucky and the destination of the original Wilderness Road. The fort withstood a ten-day siege by British and Shawnee forces in 1778."},
    {"name": "Lexington, KY", "latitude": 38.0406, "longitude": -84.5037, "trails": ["Wilderness Road / Boone's Trace"], "confidence": 0.9, "description": "Named in 1775 for the opening battle of the American Revolution, Lexington quickly became the largest and most prosperous city in Kentucky and the 'Athens of the West.' It was the natural destination for settlers who poured through the Cumberland Gap on the Wilderness Road."},
    # Great Wagon Road
    {"name": "Winchester, VA", "latitude": 39.1857, "longitude": -78.1633, "trails": ["Great Wagon Road"], "confidence": 0.9, "description": "Located at the northern end of the Shenandoah Valley, Winchester was a major colonial waypoint on the Great Wagon Road and a strategic location contested multiple times during the Civil War. George Washington used it as a headquarters during the French and Indian War."},
    {"name": "Staunton, VA", "latitude": 38.1496, "longitude": -79.0717, "trails": ["Great Wagon Road"], "confidence": 0.85, "description": "Staunton was the principal trading center of the central Shenandoah Valley and an important stop on the Great Wagon Road as emigrants moved southward into the Carolinas. It became the birthplace of Woodrow Wilson and a center of culture in the Virginia backcountry."},
    {"name": "Roanoke, VA", "latitude": 37.2710, "longitude": -79.9420, "trails": ["Great Wagon Road"], "confidence": 0.85, "description": "Situated at the southern end of the Shenandoah Valley where the Great Wagon Road turned into the Carolina piedmont, the Roanoke area was a key junction point. The town grew dramatically after the railroad arrived in the 1880s, transforming from a small village into a regional hub."},
    {"name": "Salem, NC", "latitude": 36.0726, "longitude": -80.2423, "trails": ["Great Wagon Road"], "confidence": 0.85, "description": "Founded by Moravian settlers in 1766 as a planned community along the Great Wagon Road, Salem (later joined with Winston to form Winston-Salem) was a notable exception to the rough frontier settlements of the Carolina backcountry. The Moravians maintained strict community records that provide detailed accounts of travel and trade on the road."},
    {"name": "Charlotte, NC", "latitude": 35.2271, "longitude": -80.8431, "trails": ["Great Wagon Road"], "confidence": 0.85, "description": "Settled predominantly by Scots-Irish immigrants who traveled the Great Wagon Road, Charlotte was the site of the Mecklenburg Declaration of Independence in May 1775 and the Cornwallis occupation during the Revolutionary War. The town sat at the intersection of the Great Wagon Road and the Carolina trading path."},
    {"name": "Camden, SC", "latitude": 34.2465, "longitude": -80.6070, "trails": ["Great Wagon Road"], "confidence": 0.8, "description": "Established as Fredericksburg Township in 1733 for German and Swiss settlers moving down the Great Wagon Road, Camden was the British base of operations in the South during the Revolutionary War. The devastating American defeat at the Battle of Camden in 1780 was a major British victory."},
    {"name": "Augusta, GA", "latitude": 33.4735, "longitude": -81.9748, "trails": ["Great Wagon Road"], "confidence": 0.85, "description": "The southern terminus of the Great Wagon Road, Augusta was one of colonial Georgia's most important cities and a major trading center with the Cherokee and Creek nations. It served as Georgia's capital during the Revolutionary War and remained a key inland port on the Savannah River."},
    # Chisholm Trail
    {"name": "San Antonio, TX", "latitude": 29.4241, "longitude": -98.4936, "trails": ["Chisholm Trail", "Goodnight-Loving Trail", "Western Trail / Dodge City Trail", "King's Highway / El Camino Real de los Tejas"], "confidence": 0.9, "description": "San Antonio was the starting point for most cattle drives up the Chisholm Trail, with ranchers gathering their herds in the surrounding Hill Country for the long drive north. The city's Alamo Mission and the surrounding missions represented the northern frontier of Spanish colonization in Texas."},
    {"name": "Waco, TX", "latitude": 31.5493, "longitude": -97.1469, "trails": ["Chisholm Trail"], "confidence": 0.85, "description": "The Chisholm Trail crossing of the Brazos River at Waco was one of the most critical fords on the entire cattle drive route, with herds sometimes waiting days for flood waters to recede. The suspension bridge built here in 1870 was at the time the longest single-span bridge in the United States."},
    {"name": "Fort Worth, TX", "latitude": 32.7254, "longitude": -97.3208, "trails": ["Chisholm Trail", "Western Trail / Dodge City Trail"], "confidence": 0.9, "description": "Fort Worth grew from a military post into a thriving cowtown as the 'last stop before the frontier' on the Chisholm Trail. The city's famous Hell's Half Acre district provided cowboys with rowdy entertainment, and the Stockyards district remains a tribute to Fort Worth's cattle heritage."},
    {"name": "Gainesville, TX", "latitude": 33.6218, "longitude": -97.1331, "trails": ["Chisholm Trail"], "confidence": 0.8, "description": "Gainesville was the last major Texas town on the Chisholm Trail before crossing the Red River into Indian Territory, and served as a final outfitting point for cattle drives. The Red River crossing just north of here was one of the most challenging river crossings on the entire Chisholm Trail."},
    {"name": "Red River Station, TX", "latitude": 33.9000, "longitude": -97.7000, "trails": ["Chisholm Trail"], "confidence": 0.8, "description": "The Red River Station crossing was the gateway from Texas into Indian Territory and the open range of the northern Chisholm Trail. The crossing required careful management of longhorns, and many cattlemen paid Native American tolls for passage through their lands."},
    {"name": "Caldwell, KS", "latitude": 37.0355, "longitude": -97.6109, "trails": ["Chisholm Trail"], "confidence": 0.85, "description": "Known as the 'Border Queen,' Caldwell sat on the Kansas-Indian Territory line and was the last and wildest cattle town on the Chisholm Trail after Wichita's shipping trade declined. Its proximity to the open range of Indian Territory made it a late-era railhead for Texas cattle drives."},
    {"name": "Wichita, KS", "latitude": 37.6872, "longitude": -97.3301, "trails": ["Chisholm Trail"], "confidence": 0.9, "description": "Wichita was the premier cattle trading center on the Chisholm Trail from 1872 to 1876, receiving over 1.5 million cattle during its heyday as a railhead. Wyatt Earp served as a lawman here before his famous tenure in Dodge City, and the city grew from a frontier trading post to a thriving commercial center."},
    {"name": "Abilene, KS", "latitude": 38.9200, "longitude": -97.2167, "trails": ["Chisholm Trail", "Smoky Hill Trail"], "confidence": 0.9, "description": "The first great cattle town of the Kansas railheads, Abilene received its first Texas cattle drive in 1867 when Joseph McCoy built the facilities to connect Texas longhorns with the Kansas Pacific Railroad. Wild Bill Hickok served as marshal here, and the town's cattle boom ended when Kansas farmers drove out the cattle trade in 1872."},
    # Goodnight-Loving Trail
    {"name": "Fort Sumner, NM", "latitude": 34.4701, "longitude": -104.2406, "trails": ["Goodnight-Loving Trail"], "confidence": 0.85, "description": "Fort Sumner was established in 1862 to hold the Navajo and Mescalero Apache peoples at the Bosque Redondo reservation, and was the destination of Goodnight and Loving's first cattle drive in 1866. The fort became notorious for the disastrous Bosque Redondo experiment in forced relocation and is also remembered as the place where Billy the Kid was killed."},
    {"name": "Bosque Redondo, NM", "latitude": 34.4500, "longitude": -104.1500, "trails": ["Goodnight-Loving Trail"], "confidence": 0.8, "description": "The Bosque Redondo reservation was the site of a failed experiment in forced relocation, where 9,000 Navajo people were confined in miserable conditions following the Long Walk of 1864. The reservation's food requirements, supplied by Goodnight-Loving cattle drives, could never meet the needs of the starving population."},
    {"name": "Pueblo, CO", "latitude": 38.2544, "longitude": -104.6091, "trails": ["Goodnight-Loving Trail", "Cherokee Trail"], "confidence": 0.85, "description": "Situated at the confluence of the Arkansas River and Fountain Creek, Pueblo was an important trading and military post that became a major stop on the Goodnight-Loving and Cherokee Trails. It grew into a steel-producing industrial city after the railroad arrived."},
    {"name": "Denver, CO", "latitude": 39.7392, "longitude": -104.9847, "trails": ["Goodnight-Loving Trail", "Smoky Hill Trail", "Trapper's Trail / Cache Valley Trail"], "confidence": 0.9, "description": "Founded in 1858 at the confluence of Cherry Creek and the South Platte River during the Pike's Peak Gold Rush, Denver became the commercial hub of the Rocky Mountain region. Its position at the eastern foot of the Rockies made it the destination of multiple overland trails and later the 'Queen City of the Plains.'"},
    {"name": "Cheyenne, WY", "latitude": 41.1400, "longitude": -104.8202, "trails": ["Goodnight-Loving Trail"], "confidence": 0.9, "description": "Founded in 1867 as a railroad camp for the Union Pacific, Cheyenne grew explosively to become Wyoming's territorial capital. As the northern terminus of the Goodnight-Loving Trail, it received enormous cattle shipments and became one of the wealthiest cities per capita in the world during the cattle boom of the 1880s."},
    # Smoky Hill Trail
    {"name": "Fort Riley, KS", "latitude": 39.0550, "longitude": -96.7961, "trails": ["Smoky Hill Trail"], "confidence": 0.85, "description": "Established in 1853 at the confluence of the Republican and Smoky Hill Rivers, Fort Riley guarded the beginning of the Smoky Hill Trail and the Santa Fe Trail road network. George Armstrong Custer trained the 7th Cavalry here before the campaigns against the Southern Cheyenne."},
    {"name": "Fort Hays, KS", "latitude": 38.8781, "longitude": -99.3247, "trails": ["Smoky Hill Trail"], "confidence": 0.85, "description": "Built in 1865 to protect the Smoky Hill Trail and Union Pacific Railroad workers from Cheyenne and Sioux raids, Fort Hays became an important base for General Sheridan's winter campaign of 1868-69. Wild Bill Hickok served as a scout here and the nearby town of Hays City was one of the wildest frontier settlements in Kansas."},
    {"name": "Fort Wallace, KS", "latitude": 38.9167, "longitude": -101.5833, "trails": ["Smoky Hill Trail"], "confidence": 0.8, "description": "The westernmost military post in Kansas, Fort Wallace bore the brunt of Cheyenne and Sioux raids along the Smoky Hill Trail during the Indian Wars of the 1860s. The surrounding countryside saw frequent engagements, including the Battle of Beecher Island in 1868."},
    # National Road
    {"name": "Cumberland, MD", "latitude": 39.6528, "longitude": -78.7625, "trails": ["National Road / Cumberland Road"], "confidence": 0.9, "description": "The starting point of the National Road, Cumberland was selected because it was the western terminus of the Chesapeake and Ohio Canal and the easternmost point where the Allegheny Mountains could be crossed feasibly by wagon. The city became a major trans-Appalachian transportation hub."},
    {"name": "Wheeling, WV", "latitude": 40.0640, "longitude": -80.7209, "trails": ["National Road / Cumberland Road", "Zane's Trace"], "confidence": 0.9, "description": "Wheeling was the western terminus of the first segment of the National Road and the primary gateway to the Ohio Valley and beyond. Its Ohio River crossing made it the busiest transshipment point on the Road, with goods and emigrants transferring between road and river transport."},
    {"name": "Zanesville, OH", "latitude": 39.9401, "longitude": -81.9946, "trails": ["National Road / Cumberland Road", "Zane's Trace"], "confidence": 0.85, "description": "Founded by Ebenezer Zane at the Muskingum River crossing of his trace, Zanesville became an important town on both Zane's Trace and the National Road. It served as Ohio's state capital from 1810 to 1812 and was a major pottery manufacturing center."},
    {"name": "Columbus, OH", "latitude": 39.9612, "longitude": -82.9988, "trails": ["National Road / Cumberland Road"], "confidence": 0.9, "description": "Founded as Ohio's state capital in 1816 at the crossroads of the National Road and the Scioto River, Columbus was a planned governmental city that grew into the state's largest urban center. Its position on the National Road made it a major commercial and distribution hub."},
    {"name": "Indianapolis, IN", "latitude": 39.7684, "longitude": -86.1581, "trails": ["National Road / Cumberland Road"], "confidence": 0.9, "description": "Like Columbus, Indianapolis was a planned state capital founded at the intersection of the National Road and local waterways. The arrival of the National Road in 1827 transformed it from a tiny settlement into the commercial center of Indiana."},
    {"name": "Vandalia, IL", "latitude": 38.9606, "longitude": -89.1440, "trails": ["National Road / Cumberland Road"], "confidence": 0.85, "description": "The western terminus of the National Road, Vandalia served as Illinois's state capital until 1837 when the capital moved to Springfield. A young Abraham Lincoln served in the legislature here and helped vote to move the capital to his home region."},
    # Mullan Road
    {"name": "Fort Benton, MT", "latitude": 47.8211, "longitude": -110.6699, "trails": ["Mullan Road"], "confidence": 0.85, "description": "The easternmost navigable point of the Missouri River, Fort Benton was the most inland port in North America, accessible to steamboats that traveled 3,400 miles from St. Louis. As the eastern terminus of the Mullan Road it was the gateway to Montana and the northern Rockies."},
    {"name": "Helena, MT", "latitude": 46.5958, "longitude": -112.0269, "trails": ["Mullan Road", "Bozeman Road - Northern Extension"], "confidence": 0.9, "description": "Founded as Last Chance Gulch in 1864 after gold was discovered, Helena grew to become Montana's territorial and state capital. Its position on the Mullan Road made it accessible from both the Missouri River ports and the transcontinental railroad."},
    {"name": "Missoula, MT", "latitude": 46.8721, "longitude": -113.9966, "trails": ["Mullan Road"], "confidence": 0.85, "description": "Located in a strategic valley at the confluence of several rivers, Missoula was a Mullan Road waystation that grew into the commercial center of western Montana. The Hell Gate Canyon nearby was named for its use by raiding Blackfeet against the Flathead people."},
    {"name": "Coeur d'Alene, ID", "latitude": 47.6788, "longitude": -116.7800, "trails": ["Mullan Road"], "confidence": 0.85, "description": "Situated on the beautiful lake bearing its name, Coeur d'Alene was an important Mullan Road waystation between the Bitterroot Mountains and the Columbia Plateau. The area was the homeland of the Coeur d'Alene tribe, who had a tense encounter with Colonel Edward Steptoe in 1858."},
    {"name": "Walla Walla, WA", "latitude": 46.0646, "longitude": -118.3430, "trails": ["Mullan Road", "Oregon Trail"], "confidence": 0.85, "description": "Near the site of Marcus Whitman's mission (destroyed in 1847), Walla Walla became the commercial center of the southeastern Columbia Plateau and the western terminus of the Mullan Road. It was one of the most important agricultural settlements in the Pacific Northwest."},
    # Old Spanish Trail
    {"name": "Abiquiu, NM", "latitude": 36.2181, "longitude": -106.3272, "trails": ["Old Spanish Trail"], "confidence": 0.85, "description": "Abiquiu was the northern New Mexico village that served as the main departure point for Old Spanish Trail expeditions heading toward Utah and California. The town's mixed Hispanic and Genizaro (re-settled captive) population made it a gateway between Spanish colonial and indigenous worlds."},
    {"name": "Moab, UT", "latitude": 38.5733, "longitude": -109.5498, "trails": ["Old Spanish Trail"], "confidence": 0.85, "description": "The Moab area, known as the Spanish Valley, was a key crossing point of the Colorado River on the Old Spanish Trail. The dramatic red rock canyons that now draw tourists worldwide were a formidable obstacle and landmark for the trail's mule caravans."},
    {"name": "Las Vegas, NV", "latitude": 36.1699, "longitude": -115.1398, "trails": ["Old Spanish Trail"], "confidence": 0.85, "description": "The 'Meadows' of Las Vegas were a crucial water and forage stop on the Old Spanish Trail through the Mojave Desert. John C. Frémont camped here in 1844 during his second expedition, and the site later became an important waystation for mail and emigrant routes."},
    {"name": "Cajon Pass, CA", "latitude": 34.3000, "longitude": -117.4700, "trails": ["Old Spanish Trail"], "confidence": 0.8, "description": "The mountain gateway through the San Bernardino Mountains, Cajon Pass was the entry point for the Old Spanish Trail and later the Mormon Road into southern California. Through this pass flowed not only trade goods but also the notorious 'horse thief trail' used by raiders who stole California mission horses."},
    # El Camino Real de los Tejas
    {"name": "Nacogdoches, TX", "latitude": 31.6035, "longitude": -94.7256, "trails": ["King's Highway / El Camino Real de los Tejas"], "confidence": 0.85, "description": "One of the oldest towns in Texas, Nacogdoches was a major waystation on El Camino Real de los Tejas and the main Spanish administrative center in eastern Texas. Its strategic location made it a recurring flashpoint in conflicts between Spain, France, and later the United States over Texas sovereignty."},
    {"name": "San Augustine, TX", "latitude": 31.5000, "longitude": -94.1000, "trails": ["King's Highway / El Camino Real de los Tejas"], "confidence": 0.8, "description": "San Augustine was an early Texas town on the El Camino Real and one of the oldest Anglo-American settlements in Texas, earned the nickname 'Gateway to Texas' for those approaching from Louisiana. The area saw fierce competition between Spanish and American settlers in the early 19th century."},
    {"name": "Natchitoches, LA", "latitude": 31.7543, "longitude": -93.0860, "trails": ["King's Highway / El Camino Real de los Tejas", "Natchez Trace"], "confidence": 0.85, "description": "The oldest permanent European settlement in the Louisiana Purchase territory, Natchitoches was established by the French in 1714 specifically as a trading post and counter to Spanish expansion into Texas. As the eastern terminus of El Camino Real it was the gateway between the French Mississippi Valley and Spanish Texas."},
    # Nez Perce Trail
    {"name": "Wallowa Lake, OR", "latitude": 45.2833, "longitude": -117.2167, "trails": ["Nez Perce Trail - Flight of 1877"], "confidence": 0.8, "description": "The beautiful Wallowa Valley surrounding this glacial lake was the ancestral homeland of Chief Joseph's band of Nez Perce. The U.S. government's attempt to force the Nez Perce from this beloved 'Valley of the Winding Waters' to a smaller reservation triggered the Flight of 1877."},
    {"name": "Lolo Pass, MT", "latitude": 46.6333, "longitude": -114.5833, "trails": ["Nez Perce Trail - Flight of 1877"], "confidence": 0.8, "description": "Lolo Pass across the Bitterroot Mountains was a traditional Nez Perce route to the buffalo hunting grounds of Montana, used by the tribe for centuries before Lewis and Clark crossed it in 1805. During the Flight of 1877, the Nez Perce traversed this rugged mountain pass ahead of General Howard's pursuing army."},
    {"name": "Big Hole Battlefield, MT", "latitude": 45.6500, "longitude": -113.6500, "trails": ["Nez Perce Trail - Flight of 1877"], "confidence": 0.85, "description": "The Big Hole National Battlefield commemorates the surprise dawn attack by Colonel Gibbon's forces on the sleeping Nez Perce camp on August 9, 1877. Despite the ambush, the Nez Perce warriors rallied and drove off the soldiers, allowing the people to continue their flight, though with heavy casualties including many women and children."},
    {"name": "Bear Paw Battlefield, MT", "latitude": 48.0167, "longitude": -109.7500, "trails": ["Nez Perce Trail - Flight of 1877"], "confidence": 0.85, "description": "Just 40 miles from the safety of Canada, Chief Joseph and the Nez Perce were caught by General Nelson Miles at Snake Creek in October 1877. After a five-day siege in the autumn snow, Chief Joseph delivered his famous 'From where the sun now stands' surrender speech, ending one of the most brilliant military retreats in history."},
    # Cherokee Trail
    {"name": "Fort Smith, AR", "latitude": 35.3859, "longitude": -94.3985, "trails": ["Cherokee Trail"], "confidence": 0.85, "description": "Established as a military post in 1817 on the Arkansas River at the edge of Indian Territory, Fort Smith was the jumping-off point for the Cherokee Trail. The federal court established here under Judge Isaac Parker, known as the 'Hanging Judge,' was responsible for law enforcement in Indian Territory."},
    {"name": "Fort Scott, KS", "latitude": 37.8390, "longitude": -94.7050, "trails": ["Cherokee Trail"], "confidence": 0.8, "description": "An 1842 military post on the Military Road through Kansas, Fort Scott was an important waystation on the Cherokee Trail as it passed through eastern Kansas. The surrounding area was a violent battleground during the 'Bleeding Kansas' era as pro- and anti-slavery forces fought for control."},
    # Applegate Trail
    {"name": "Goose Lake, OR/CA", "latitude": 41.9800, "longitude": -120.3000, "trails": ["Applegate Trail"], "confidence": 0.75, "description": "Straddling the Oregon-California border, Goose Lake was a key landmark on the Applegate Trail where travelers could find water in the high desert. The lake's alkaline water and surrounding dry country made this a challenging stretch of the otherwise promising southern Oregon route."},
    {"name": "Klamath Falls, OR", "latitude": 42.2249, "longitude": -121.7817, "trails": ["Applegate Trail"], "confidence": 0.8, "description": "Near the ancestral territory of the Klamath and Modoc peoples, the Klamath Basin was a challenging section of the Applegate Trail that required emigrants to cross volcanic terrain and deal with hostile encounters. The area later became the scene of the Modoc War of 1872-73."},
    {"name": "Jacksonville, OR", "latitude": 42.3121, "longitude": -122.9682, "trails": ["Applegate Trail"], "confidence": 0.8, "description": "The gold rush town of Jacksonville was the first major settlement reached by emigrants on the Applegate Trail after crossing the Siskiyou Mountains. Founded after a gold discovery in Rich Gulch in 1851, it served as the seat of Jackson County and a supply point for miners throughout southwestern Oregon."},
    # Zane's Trace
    {"name": "Chillicothe, OH", "latitude": 39.3331, "longitude": -82.9824, "trails": ["Zane's Trace"], "confidence": 0.85, "description": "Chillicothe was the first and most important capital of the Northwest Territory and early Ohio, and sat on Zane's Trace at the Scioto River crossing. The area was the heart of the Shawnee nation and the site of multiple frontier conflicts before becoming Ohio's first state capital."},
    {"name": "Maysville, KY", "latitude": 38.6412, "longitude": -83.7452, "trails": ["Zane's Trace"], "confidence": 0.8, "description": "Located on the Ohio River at the southern terminus of Zane's Trace, Maysville (originally Limestone) was the landing point for emigrants who floated down the Ohio and then struck inland through Kentucky. Daniel Boone operated a ferry crossing here late in his life."},
    # Western Trail
    {"name": "Bandera, TX", "latitude": 29.7274, "longitude": -99.0740, "trails": ["Western Trail / Dodge City Trail"], "confidence": 0.8, "description": "The 'Cowboy Capital of the World,' Bandera was the southern starting point for the Western Trail, with the surrounding Hill Country ranches providing the longhorns that would be driven north to Dodge City. The Medina River crossing here was the first major water obstacle on the drive north."},
    {"name": "Dodge City, KS", "latitude": 37.7528, "longitude": -99.9659, "trails": ["Western Trail / Dodge City Trail", "Chisholm Trail"], "confidence": 0.95, "description": "The most famous cattle town in American history, Dodge City received over five million longhorns during its cattle trading peak from 1875 to 1885. Lawmen like Wyatt Earp, Bat Masterson, and Doc Holliday kept order in the 'Queen of the Cowtowns' while the Long Branch Saloon and Front Street provided entertainment."},
    {"name": "Ogallala, NE", "latitude": 41.1267, "longitude": -101.7011, "trails": ["Western Trail / Dodge City Trail"], "confidence": 0.85, "description": "Known as the 'Gomorrah of the Plains,' Ogallala was the northern terminus of the Western Trail and a shipping point for Texas cattle on the Union Pacific Railroad. Cowboys who survived the long trail drive celebrated in the town's numerous saloons before the long ride back to Texas."},
    # Gila Trail
    {"name": "El Paso, TX", "latitude": 31.7619, "longitude": -106.4850, "trails": ["Gila Trail", "Cooke's Wagon Road", "El Camino Real de Tierra Adentro", "Kearny Trail"], "confidence": 0.9, "description": "The Pass of the North at El Paso del Norte was one of the most strategic geographic and cultural crossroads in the Southwest, sitting on the Rio Grande at the boundary of modern Texas and New Mexico. The crossing here connected New Mexico to Mexico via the Camino Real and to California via the Gila Trail."},
    {"name": "Tucson, AZ", "latitude": 32.2226, "longitude": -110.9747, "trails": ["Gila Trail", "Cooke's Wagon Road"], "confidence": 0.9, "description": "Originally a Tohono O'odham village called Stjukshon, Tucson became a Spanish presidio in 1775 and remained part of Mexico until the Gadsden Purchase of 1853. As the only significant settlement between El Paso and the Colorado River, it was an essential resupply point for travelers on the Gila Trail."},
    {"name": "Yuma, AZ", "latitude": 32.6927, "longitude": -114.6277, "trails": ["Gila Trail", "Cooke's Wagon Road"], "confidence": 0.9, "description": "The Colorado River crossing at Yuma was the critical gateway between Arizona and California, one of the most difficult river crossings in the Southwest. The Yuma Crossing was controlled for centuries by the Quechan people, who charged tolls for passage; the U.S. Army established Fort Yuma here in 1850 to keep the crossing open."},
    {"name": "San Diego, CA", "latitude": 32.7153, "longitude": -117.1610, "trails": ["Gila Trail", "Cooke's Wagon Road"], "confidence": 0.9, "description": "The destination of the southern overland routes, San Diego was California's oldest European settlement and a rapidly growing port after the Mexican-American War. The Mormon Battalion's arrival here in January 1847 completed the first wagon crossing from New Mexico to the Pacific Ocean."},
    # Hastings Cutoff / Donner
    {"name": "Donner Lake, CA", "latitude": 39.3200, "longitude": -120.2400, "trails": ["Donner Pass Route", "Hastings Cutoff"], "confidence": 0.9, "description": "The small lake at the foot of Donner Pass became forever associated with the tragedy of the Donner-Reed Party, which was stranded here from October 1846 to April 1847. The party's ordeal, in which 41 of 87 people perished and survivors resorted to cannibalism, became the most infamous episode in the history of overland emigration."},
    {"name": "Salt Lake Desert, UT", "latitude": 40.7608, "longitude": -113.0000, "trails": ["Hastings Cutoff"], "confidence": 0.75, "description": "The Great Salt Lake Desert was the most treacherous section of the Hastings Cutoff, a 80-mile crossing with no water or forage that the Donner-Reed Party underestimated disastrously. The party spent five days crossing what Hastings had claimed could be done in two, losing most of their livestock and abandoning wagons."},
    # Lander Road
    {"name": "Pacific Springs, WY", "latitude": 42.5000, "longitude": -109.2000, "trails": ["Lander Road / Lander Cutoff", "Oregon Trail"], "confidence": 0.8, "description": "Pacific Springs, just west of South Pass, was the first water emigrants found on the Pacific slope of the Continental Divide and the departure point for multiple cutoffs including the Lander Road. The cold, clear springs provided critical relief after the dry crossing of South Pass."},
    # Pony Express additional
    {"name": "Hollenberg Station, KS", "latitude": 39.9000, "longitude": -97.0000, "trails": ["Pony Express Route"], "confidence": 0.8, "description": "The Hollenberg Pony Express Station in northeastern Kansas is the only known unaltered original Pony Express station still standing in its original location. Built by Gerat Hollenberg in 1857 as a ranch and trading post, it served as a home station on the Missouri-Kansas stretch of the route."},
    # Trapper's Trail
    {"name": "Taos, NM", "latitude": 36.4072, "longitude": -105.5731, "trails": ["Trapper's Trail / Cache Valley Trail", "Old Spanish Trail"], "confidence": 0.85, "description": "Taos was the mountain men's winter headquarters and social center, where trappers like Kit Carson, Jim Bridger, and Ceran St. Vrain gathered each year. The Taos Rebellion of 1847 against American occupation killed the first American territorial governor of New Mexico."},
    # Historic Forts
    {"name": "Fort Leavenworth, KS", "latitude": 39.3600, "longitude": -94.9100, "trails": ["Kearny Trail", "Oregon Trail"], "confidence": 0.9, "description": "Established in 1827 as the oldest active U.S. Army post west of the Mississippi River, Fort Leavenworth was the staging point for Kearny's Army of the West in 1846 and a major supply depot for military operations throughout the West. It guarded the Missouri River crossing that began the overland routes to Santa Fe and the Pacific."},
    # Additional landmarks
    {"name": "Horsehead Crossing, TX", "latitude": 31.5000, "longitude": -102.4000, "trails": ["Goodnight-Loving Trail"], "confidence": 0.8, "description": "The Horsehead Crossing of the Pecos River was named for the horse skulls left by animals that drank greedily of the alkali-tainted water and died. Charles Goodnight chose this remote and unforgiving crossing as the route for his first cattle drive to avoid Comanche raiders on the Llano Estacado."},
    {"name": "Pecos, TX", "latitude": 31.4200, "longitude": -103.4900, "trails": ["Goodnight-Loving Trail"], "confidence": 0.8, "description": "The crossing of the Pecos River was a critical waypoint on the Goodnight-Loving Trail, where the cattle could be rested after the brutal waterless stretch from the Colorado River. The Pecos River valley provided the water and forage corridor that made the trail feasible."},
    {"name": "Raton, NM", "latitude": 36.9000, "longitude": -104.4400, "trails": ["Goodnight-Loving Trail", "Santa Fe Trail"], "confidence": 0.85, "description": "The town at the foot of Raton Pass was a major waystation on both the Goodnight-Loving Trail and the Mountain Branch of the Santa Fe Trail. Dick Wootton's toll road through the pass was replaced by the Atchison, Topeka and Santa Fe Railway in 1879, and Raton grew as a railroad coal mining town."},
    {"name": "Ash Hollow, NE", "latitude": 41.8500, "longitude": -102.3000, "trails": ["Oregon Trail", "California Trail"], "confidence": 0.85, "description": "Ash Hollow, where the north and south forks of the Platte River diverged, was a famous resting spot on the Oregon and California Trails, with fresh water, wood, and grass after the dry crossing of the Nebraska plains. A violent confrontation here in 1855 between U.S. troops and Brulé Lakota people marked the beginning of the great Sioux wars."},
    {"name": "South Pass City, WY", "latitude": 42.5069, "longitude": -108.7988, "trails": ["Oregon Trail", "California Trail"], "confidence": 0.8, "description": "A gold rush town established near South Pass in 1867, South Pass City was briefly an important Wyoming Territory settlement and the site where Esther Hobart Morris championed women's suffrage legislation, making Wyoming the first territory to grant women the right to vote in 1869."},
    {"name": "Scotts Bluff Pass, NE", "latitude": 41.8200, "longitude": -103.6900, "trails": ["Oregon Trail", "California Trail"], "confidence": 0.85, "description": "Mitchell Pass through the Scotts Bluff formation was the narrow gap through which the Oregon Trail was routed after a better route was found in the 1850s. Deep wagon ruts are still visible in the soft soil on either side of the pass, preserved within Scotts Bluff National Monument."},
    {"name": "Alcove Spring, KS", "latitude": 39.7000, "longitude": -96.6200, "trails": ["Oregon Trail", "Mormon Trail"], "confidence": 0.8, "description": "Alcove Spring was a beautiful natural spring near the Big Blue River crossing on the Oregon and Mormon Trails. Sarah Keyes, an elderly member of the Donner-Reed Party, died and was buried here in May 1846, the first of many who would perish before the party reached California."},
    {"name": "Big Blue River Crossing, KS", "latitude": 39.6700, "longitude": -96.6500, "trails": ["Oregon Trail", "California Trail", "Mormon Trail"], "confidence": 0.8, "description": "The Big Blue River crossing was the first major river obstacle on the Oregon and California Trails, sometimes requiring emigrants to use improvised ferries or rafts when the river was in flood. The marshy bottomlands here delayed many wagon trains during the critical spring departure season."},
    {"name": "Courthouse Rock, NE", "latitude": 41.5800, "longitude": -103.0800, "trails": ["Oregon Trail", "California Trail"], "confidence": 0.85, "description": "Courthouse Rock and adjacent Jail Rock were dramatic buttes rising from the North Platte valley that served as trail landmarks for Oregon and California-bound emigrants. Many emigrants noted them in their diaries, often trying and failing to estimate their actual distance from the trail."},
    {"name": "Platte River Road, NE", "latitude": 41.1000, "longitude": -101.0000, "trails": ["Oregon Trail", "California Trail", "Mormon Trail", "Pony Express Route"], "confidence": 0.85, "description": "The Platte River Road along the shallow, braided Platte River was the highway of the Great Plains migration, carrying the overwhelming majority of westbound emigrants for three decades. The river valley provided water, grass, and a relatively level pathway across the seemingly endless plains."},
    {"name": "Fort McPherson, NE", "latitude": 41.0500, "longitude": -100.5800, "trails": ["Oregon Trail", "Pony Express Route"], "confidence": 0.8, "description": "Established in 1863 to protect the Platte River emigrant road and the Pony Express, Fort McPherson was an important base for campaigns against Sioux and Cheyenne raiders during the 1860s. Buffalo Bill Cody served as a scout here and the fort cemetery contains many victims of the Indian Wars."},
    {"name": "Rock Creek Station, NE", "latitude": 40.1500, "longitude": -97.0000, "trails": ["Oregon Trail", "Pony Express Route"], "confidence": 0.8, "description": "Rock Creek Station was a Pony Express relay station and Oregon Trail waystation in southeastern Nebraska that became famous as the site where 'Wild Bill' Hickok killed David McCanles in 1861 in a still-disputed confrontation. The station's well-worn ruts show the heavy traffic of overland emigration."},
    {"name": "Emigrant Gap, CA", "latitude": 39.2800, "longitude": -120.6700, "trails": ["California Trail", "Donner Pass Route"], "confidence": 0.8, "description": "Emigrant Gap was the passage into the Sierra Nevada foothills used by California Trail emigrants before they tackled the final ascent to Donner or Carson Pass. The dramatic view from the gap looking west into the Sacramento Valley was the first sight of California's promised golden lands for many weary travelers."},
    {"name": "Johnson's Ranch, CA", "latitude": 39.1500, "longitude": -121.2000, "trails": ["California Trail", "Donner Pass Route"], "confidence": 0.75, "description": "Johnson's Ranch on Bear Creek was the first settlement reached by emigrants descending from the Sierra Nevada into the Sacramento Valley, and the staging point for the relief parties sent up to rescue the stranded Donner Party. William Johnson's hospitality to exhausted emigrants made his ranch one of the most welcome sights on the entire overland route."},
    {"name": "Rabbit Ears Pass, CO", "latitude": 40.3800, "longitude": -106.6000, "trails": ["Cherokee Trail", "Trapper's Trail / Cache Valley Trail"], "confidence": 0.75, "description": "Named for the distinctive twin peaks visible for miles, Rabbit Ears Pass was a landmark crossing of the Park Range used by trappers and the Cherokee Trail. The pass provided a route through the mountains between the North Park and the Yampa River valley."},
    {"name": "Pawnee Rock, KS", "latitude": 38.2700, "longitude": -98.9800, "trails": ["Santa Fe Trail"], "confidence": 0.85, "description": "Pawnee Rock was one of the most distinctive landmarks on the Santa Fe Trail, a large sandstone outcropping that rose above the flat Kansas plains and served as a lookout point and inscription rock. Many emigrant parties carved their names into the soft stone, and it was a frequent campsite and reported site of attacks by Pawnee warriors."},
    {"name": "Point of Rocks, NM", "latitude": 36.7500, "longitude": -104.0000, "trails": ["Santa Fe Trail"], "confidence": 0.8, "description": "Point of Rocks in the Canadian River valley was an important water source and camping spot on the Santa Fe Trail's Cimarron Cutoff, providing a rare opportunity for rest in the dry country. The dramatic rock formation was also used as an ambush site by Jicarilla Apache and Comanche warriors who preyed on the trail's commercial traffic."},
    {"name": "Jornada del Muerto, NM", "latitude": 33.0000, "longitude": -107.0000, "trails": ["El Camino Real de Tierra Adentro"], "confidence": 0.8, "description": "The 90-mile 'Journey of the Dead Man' was the most fearsome section of El Camino Real de Tierra Adentro, a waterless desert stretch that killed many travelers who attempted to cross it without adequate preparation. The Oñate colonists first crossed it in 1598 and subsequent travelers both dreaded and narrated the crossing for centuries."},
    {"name": "Mesilla, NM", "latitude": 32.2724, "longitude": -106.8030, "trails": ["El Camino Real de Tierra Adentro", "Gila Trail"], "confidence": 0.85, "description": "The Mexican village of Mesilla was transferred to the United States as part of the Gadsden Purchase of 1853 and became an important hub on the southern overland routes. Billy the Kid was tried and convicted here in 1881, and the historic plaza still preserves its 19th-century character."},
    {"name": "Fort Craig, NM", "latitude": 33.5200, "longitude": -107.1800, "trails": ["El Camino Real de Tierra Adentro"], "confidence": 0.8, "description": "Established in 1854 near the northern end of the Jornada del Muerto, Fort Craig was the scene of the largest Civil War battle in the New Mexico Territory at Valverde in 1862, where Confederate forces under General Sibley attempted to capture New Mexico as part of the Confederacy's western strategy."},
    {"name": "Fort Defiance, AZ", "latitude": 35.7500, "longitude": -109.0600, "trails": ["Old Spanish Trail"], "confidence": 0.75, "description": "Established in 1851 as the first permanent U.S. Army post in Arizona, Fort Defiance was built in the heart of Navajo territory after the Mexican-American War. It became the administrative center for Navajo affairs and the starting point of the Long Walk of 1864 that forced the Navajo people to Bosque Redondo."},
    {"name": "South Platte River Crossing, CO", "latitude": 40.6700, "longitude": -103.2000, "trails": ["Oregon Trail", "California Trail", "Pony Express Route"], "confidence": 0.8, "description": "The crossing of the South Platte River was one of the most challenging early obstacles on the overland trails, with the wide, shallow river hiding quicksand and unstable footing for wagons and livestock. Emigrants at this crossing had to decide whether to continue straight north or angle westward along the river."},
    {"name": "Fetterman Massacre Site, WY", "latitude": 44.5100, "longitude": -106.9200, "trails": ["Bozeman Trail"], "confidence": 0.85, "description": "The site of the Fetterman Fight on December 21, 1866, where Lakota, Cheyenne, and Arapaho warriors under Crazy Horse and High Back Bone lured Lt. Col. William Fetterman and 80 soldiers into an ambush and killed them all. The disaster led directly to the Fort Laramie Treaty of 1868 and U.S. abandonment of the Bozeman Trail forts."},
    {"name": "Crossing of the Platte, WY", "latitude": 42.8500, "longitude": -106.3200, "trails": ["Oregon Trail", "California Trail", "Mormon Trail", "Pony Express Route"], "confidence": 0.8, "description": "The upper crossing of the North Platte River at the site of present-day Casper, Wyoming was a critical junction where emigrants crossed to the south bank or paid for ferry service. The Mormon Ferry established here in 1847 was one of the first businesses operated by Latter-day Saints along the trail."},
    {"name": "Whitman Mission, WA", "latitude": 46.0400, "longitude": -118.4700, "trails": ["Oregon Trail"], "confidence": 0.85, "description": "Marcus and Narcissa Whitman's Waiilatpu Mission near Walla Walla was an important resupply point for Oregon Trail emigrants from 1836 until the Cayuse attacked and killed the Whitmans and eleven others in 1847. The Whitman Massacre triggered the Cayuse War and accelerated calls for U.S. territorial government in Oregon."},
]


def scrape_trail_list(url):
    """Fetch a remote JSON resource and return a parsed list, or empty list on failure.

    Intended for optionally supplementing the hardcoded TRAILS data with an
    external source (e.g. a JSON API endpoint).  Not called by default; all
    data is already hardcoded in the TRAILS and LANDMARKS constants above.
    """
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = response.read().decode("utf-8")
            return json.loads(data)
    except Exception:
        return []


def build_geojson(trails):
    """Build a GeoJSON FeatureCollection from the trails list."""
    features = []
    for trail in trails:
        feature = {
            "type": "Feature",
            "properties": {
                "name": trail["name"],
                "type": "trail",
                "source": "seed:historic_trails",
                "years": trail["years"],
                "description": trail["description"],
            },
            "geometry": {
                "type": "LineString",
                "coordinates": trail["coordinates"],
            },
        }
        features.append(feature)
    return {"type": "FeatureCollection", "features": features}


def main():
    parser = argparse.ArgumentParser(
        description="Generate historic trails GeoJSON and landmarks JSON."
    )
    parser.add_argument(
        "--output-dir",
        default="data",
        help="Directory to write output files (default: data)",
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    trails_path = os.path.join(args.output_dir, "historic_trails.geojson")
    geojson = build_geojson(TRAILS)
    with open(trails_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(geojson, indent=2))
    print(f"Wrote {len(geojson['features'])} trails to {trails_path}")

    landmarks_path = os.path.join(args.output_dir, "historic_trail_landmarks.json")
    landmarks_out = [
        {
            "name": lm["name"],
            "type": "trail_landmark",
            "latitude": lm["latitude"],
            "longitude": lm["longitude"],
            "description": lm["description"],
            "source": "seed:historic_trail_landmarks",
            "confidence": lm["confidence"],
            "trails": lm["trails"],
        }
        for lm in LANDMARKS
    ]
    with open(landmarks_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(landmarks_out, indent=2))
    print(f"Wrote {len(landmarks_out)} landmarks to {landmarks_path}")


if __name__ == "__main__":
    main()
