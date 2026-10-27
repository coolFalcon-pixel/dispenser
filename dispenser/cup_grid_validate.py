"""Experimental full-grid pattern validator. NO motor or GPIO control.
Run: python3 cup_grid_validate.py
Uses 26 retained captures. Does not estimate cup boundaries or water height.
"""
import json
from pathlib import Path
from statistics import median
from time import monotonic, sleep
from datetime import datetime
FIELDS = ('distance_mm','target_status','nb_target_detected','signal_per_spad',
          'ambient_per_spad','range_sigma_mm','reflectance','nb_spads_enabled')
EXAMPLES = [{'label': 'no_cup', 'grid': [184.75, 192.625, 199.125, 201.0, 204.375, 222.25, 242.625, 291.125, 180.375, None, None, None, None, 280.625, 291.75, 308.25, 180.75, 190.125, None, None, 276.125, 284.875, 296.0, 310.625, 170.875, 175.25, None, None, 275.125, 288.0, 298.875, 315.0, 108.75, 109.0, 147.5, None, 280.25, 292.125, 304.125, 317.25, 178.125, 206.0, 232.125, 258.625, 283.625, 296.5, 310.5, 313.375, 213.5, 223.75, 247.0, 264.0, 285.25, 299.875, 315.625, 329.0, 40.25, 226.0, 248.875, 268.25, 289.0, 303.5, 319.75, 333.875]}, {'label': 'no_cup', 'grid': [184.375, 192.5, 198.625, 201.0, 205.25, 221.875, 242.125, 291.25, 181.625, None, None, None, None, 280.875, 290.625, 308.125, 183.0, 192.125, None, None, 274.0, 284.5, 296.375, 311.375, 169.75, 174.25, None, None, 274.625, 287.75, 299.0, 314.75, 111.5, 107.125, None, None, 281.125, 292.5, 303.625, 317.0, 178.25, 206.875, 230.75, 259.25, 284.625, 296.5, 310.375, 313.75, 212.875, 223.25, 246.125, 264.125, 285.25, 299.75, 315.0, 329.0, 44.875, 226.375, 249.0, 269.75, 289.5, 304.0, 321.5, 332.875]}, {'label': 'no_cup', 'grid': [185.875, 192.625, 200.125, 202.375, 205.5, 222.125, 242.75, 290.625, 181.375, None, None, None, None, 281.5, 292.5, 308.0, 182.625, 193.5, None, None, 274.75, 285.5, 296.0, 311.375, 169.25, 174.0, None, None, 275.875, 288.5, 300.0, 315.75, 107.875, 108.625, None, None, 280.25, 292.5, 304.5, 317.875, 178.125, 206.125, 230.125, 260.375, 284.875, 296.875, 311.0, 314.375, 213.5, 224.0, 247.5, 264.125, 285.875, 300.375, 316.375, 329.75, 45.5, 226.75, 250.0, 268.75, 289.25, 303.5, 321.875, 334.0]}, {'label': 'empty_cup', 'grid': [None, None, None, 235.375, None, 223.0, 242.75, 291.375, None, None, None, None, None, 281.0, 291.75, 307.0, 190.375, None, None, 219.75, None, 284.625, 295.5, 310.125, 191.0, None, None, None, None, 287.375, 298.625, 314.25, 200.25, None, None, None, None, 291.5, 303.625, 317.0, 191.625, 230.75, 255.5, None, None, 296.0, None, None, 214.0, 224.5, 246.75, 262.75, 285.0, None, None, None, 49.75, 227.0, 249.5, 268.25, None, None, None, None]}, {'label': 'empty_cup', 'grid': [None, 224.75, 232.25, 234.0, 211.625, 223.75, 243.25, 290.5, None, None, None, None, None, 280.75, 291.875, 308.75, 191.25, 199.5, None, 222.125, 246.0, 284.0, 295.75, 310.75, 189.375, 188.75, None, None, 265.25, 288.125, 299.125, 315.5, 182.625, 188.75, None, None, 283.875, 292.0, 303.5, 317.0, 188.625, 233.625, 261.625, 269.5, 283.375, 296.125, 310.25, 313.75, 213.875, 223.875, 246.0, 264.125, 286.0, 299.25, 315.75, 329.0, 50.125, 227.125, 249.75, 271.125, 288.875, 304.0, None, None]}, {'label': 'empty_cup', 'grid': [None, 222.375, 233.0, 234.75, 211.5, 223.375, 243.0, 289.375, None, None, None, None, None, 281.0, 291.0, 308.875, 191.625, 199.875, None, 222.125, 246.75, 283.875, 296.125, 311.25, 189.625, 189.125, None, None, 263.75, 287.75, 299.375, 316.0, 182.5, 188.0, None, None, 283.875, 292.125, 303.25, 316.875, 188.375, 234.25, 262.125, 269.25, 284.5, 296.25, 310.25, 314.125, 211.75, 225.25, 248.625, 263.25, 285.875, 299.75, 315.125, 328.75, 52.625, 226.25, 249.125, 270.625, 288.75, 304.5, None, None]}, {'label': 'empty_cup', 'grid': [None, None, None, None, None, None, 243.25, None, None, None, None, 220.5, None, None, None, None, 192.5, None, None, 218.875, None, 284.5, 296.0, None, 194.125, None, None, None, None, 287.5, None, None, None, None, None, None, None, 290.25, None, None, 191.375, 235.75, 247.75, None, None, None, None, None, 214.0, 225.125, 247.25, 264.375, None, None, None, None, 54.625, 227.0, 249.5, None, None, None, None, None]}, {'label': 'empty_cup', 'grid': [None, None, None, None, None, None, 243.25, None, None, None, None, 219.875, None, None, None, None, 192.25, None, None, 219.625, None, 284.5, 295.375, None, 194.25, None, None, None, None, 286.875, None, None, None, None, None, None, None, None, None, None, 193.125, 236.0, 248.75, None, None, None, None, None, 214.0, 225.125, 247.125, 263.25, None, None, None, None, 53.375, 228.125, 249.125, None, None, None, None, None]}, {'label': 'low_water', 'grid': [194.75, 226.5, 223.5, 216.0, 210.75, 224.875, 244.625, 290.125, 237.0, None, None, 254.875, 273.875, 281.875, 292.125, 309.25, 209.625, 206.625, None, 243.75, 264.375, 286.75, 297.75, 310.75, 203.75, 195.375, 223.625, 249.5, 271.25, 288.5, 300.75, 315.0, 229.25, 221.75, 240.75, 254.875, 285.125, 293.625, 304.625, 314.5, 194.875, 235.0, 257.25, 266.375, 287.25, 297.5, 307.625, 309.375, 214.5, 226.75, 249.5, 268.375, 287.875, 300.75, 314.5, 325.5, 47.75, 227.625, 252.375, 273.875, 289.75, 303.75, 319.0, 329.375]}, {'label': 'low_water', 'grid': [192.25, 226.375, 218.375, 216.25, 212.0, 226.0, 245.0, 289.75, 233.5, None, None, 262.125, 278.875, 282.5, 292.0, 308.375, 206.25, 207.5, None, 259.75, 274.5, 286.875, 297.5, 311.0, 214.25, 195.0, None, 255.375, 267.875, 287.0, 300.375, 311.875, 238.875, 241.5, 248.25, 254.375, 280.75, 294.875, 305.875, 298.375, 207.375, 232.0, 260.125, 274.875, 286.875, 297.5, 299.75, 281.0, 214.375, 227.0, 251.5, 268.0, 288.375, 299.625, 284.375, 253.625, 52.0, 228.625, 251.75, 274.5, 290.125, 303.75, 280.375, 239.625]}, {'label': 'low_water', 'grid': [193.5, 227.125, 220.5, 219.625, 212.875, 226.875, 245.25, 290.625, 234.125, None, None, 262.875, 278.875, 282.875, 292.625, 308.25, 205.25, 207.875, None, 260.875, 274.375, 287.375, 297.375, 310.625, 215.875, 193.5, None, 255.25, 267.125, 287.75, 301.0, 311.75, 239.125, 235.375, 247.625, 254.875, 283.875, 295.25, 304.875, 294.25, 207.75, 232.0, 261.375, 275.625, 287.875, 298.0, 299.25, 272.875, 215.0, 228.5, 252.75, 270.0, 289.375, 296.625, 276.125, 247.25, 47.75, 228.5, 252.625, 275.375, 291.25, 296.875, 258.0, 228.25]}, {'label': 'low_water', 'grid': [192.75, 230.25, 221.875, 225.0, 217.875, 226.0, 245.125, 291.0, 231.0, None, None, 261.875, 282.375, 284.0, 292.25, 309.125, 209.375, 206.875, None, 259.125, 275.75, 288.0, 298.0, 310.875, 241.0, 189.375, None, 248.5, 264.375, 290.0, 301.0, 311.625, 242.75, 232.125, 258.875, 271.25, 286.375, 295.625, 305.875, 294.125, 192.125, 242.125, 256.625, 277.375, 289.25, 298.5, 298.125, 274.5, 216.875, 226.875, 251.5, 269.0, 289.75, 297.5, 278.625, 248.25, 51.125, 228.5, 252.75, 275.0, 290.875, 298.875, 261.25, 231.25]}, {'label': 'low_water', 'grid': [194.625, 228.0, 220.375, 224.375, 214.25, 227.75, 245.375, 290.375, 236.625, None, None, 266.875, 283.0, 282.875, 293.0, 308.375, 203.25, 206.75, None, 257.625, 276.5, 287.125, 297.75, 311.375, 217.5, 191.5, None, 246.125, 265.125, 289.375, 301.0, 311.5, 245.5, 216.625, 255.625, 264.75, 284.875, 296.25, 304.875, 294.125, 204.25, 239.125, 258.25, 276.875, 288.375, 298.25, 298.0, 275.25, 214.125, 228.125, 252.0, 269.625, 289.0, 298.125, 278.0, 248.375, 50.625, 229.375, 251.875, 273.5, 291.375, 299.25, 260.75, 231.625]}, {'label': 'middle_water', 'grid': [190.375, 233.125, 248.875, 238.5, 220.0, 226.25, 245.875, 292.375, 227.125, None, None, 267.125, 279.125, 283.5, 293.375, 309.125, 204.125, 208.625, None, 246.625, 244.375, 279.75, 298.25, 311.5, 191.625, 196.75, None, 250.375, 266.0, 290.125, 301.75, 311.75, 213.375, 147.75, 240.5, 276.25, 285.875, 296.375, 304.625, 294.375, 190.625, 228.5, 254.5, 278.0, 289.125, 298.625, 298.0, 275.5, 213.5, 227.125, 249.875, 269.0, 289.875, 297.875, 278.0, 248.0, 48.875, 227.625, 252.125, 272.375, 291.75, 299.75, 261.5, 231.625]}, {'label': 'middle_water', 'grid': [195.5, 233.5, 242.5, 229.875, 214.75, 226.125, 245.625, 292.25, 241.5, None, None, 273.0, 276.5, 284.0, 293.75, 309.125, 196.25, 208.125, None, 250.0, 261.375, 287.0, 298.25, 312.125, 186.375, 191.125, None, 249.25, 256.875, 286.25, 301.75, 312.125, 115.0, 123.25, 224.5, 275.75, 287.0, 295.875, 306.125, 294.5, 192.625, 231.875, 254.125, 278.25, 289.5, 299.0, 298.0, 275.25, 215.25, 228.0, 251.5, 269.75, 290.25, 298.25, 278.5, 248.625, 48.625, 227.625, 252.25, 274.125, 291.625, 299.75, 261.0, 231.0]}, {'label': 'middle_water', 'grid': [None, 231.75, 238.25, 224.25, 210.75, 226.0, 245.0, 291.5, 234.0, 233.375, 238.75, 265.5, 266.125, 281.25, 292.5, 309.25, 162.125, 198.75, None, 243.25, 260.75, 285.5, 296.75, 310.75, 165.25, None, None, 238.75, 261.25, 288.5, 299.5, 310.5, None, None, 225.25, 268.5, 280.25, 294.25, 302.5, 291.0, 202.0, 233.25, 251.0, 276.25, 287.5, 296.75, 297.0, 273.0, None, 227.0, 251.0, 266.25, 287.0, 295.75, 276.5, 248.0, 59.0, 228.0, 249.25, 273.5, 289.5, 297.5, 260.75, 231.0]}, {'label': 'middle_water', 'grid': [199.625, 246.0, 238.625, 231.5, 212.375, 226.25, 245.875, 293.0, 253.625, 246.375, None, 269.5, 276.75, 283.25, 293.5, 309.875, 193.875, 205.75, None, 240.25, 252.125, 287.75, 298.5, 312.0, 182.5, 186.25, None, 252.625, 265.875, 290.5, 301.75, 312.375, 107.25, 121.875, None, 282.5, 291.5, 295.875, 306.0, 295.0, 189.875, 234.125, 254.625, 276.5, 290.0, 299.25, 297.875, 275.875, 216.75, 227.5, 252.0, 268.5, 290.25, 298.125, 279.0, 248.75, 48.875, 228.875, 251.25, 274.75, 292.0, 299.75, 261.25, 231.375]}, {'label': 'middle_water', 'grid': [200.75, 231.125, 235.375, 218.0, 210.25, 226.0, 244.125, 291.875, 247.0, 242.25, 254.25, 262.0, 273.5, 282.5, 293.875, 309.125, 163.25, 203.5, None, 239.75, 258.75, 286.75, 297.5, 310.75, 166.25, None, None, 236.625, 263.75, 289.0, 301.25, 311.75, 210.0, 204.75, 218.25, 268.25, 282.375, 295.5, 304.875, 293.125, 188.75, 236.25, 254.375, 270.875, 287.5, 297.125, 297.0, 274.375, 192.625, 229.25, 251.875, 268.5, 288.5, 297.25, 276.625, 248.125, 55.125, 228.5, 251.5, 272.625, 290.125, 299.25, 261.5, 231.5]}, {'label': 'stop_level', 'grid': [215.0, 238.5, 239.75, 222.0, 210.75, 226.5, 245.0, 291.0, 251.5, None, None, None, 270.75, 282.75, 293.0, 309.25, 151.875, None, None, 241.0, 261.25, 287.0, 297.75, 311.0, 154.0, None, None, 250.5, 272.5, 290.25, 301.25, 312.75, 245.5, None, None, 268.0, 286.25, 295.75, 305.25, 293.25, 191.875, 222.0, 244.5, 269.75, 287.75, 298.0, 298.25, 274.0, 197.0, 226.25, 249.25, 267.75, 288.5, 297.25, 278.0, 248.25, 54.375, 228.75, 250.25, 273.0, 290.0, 299.25, 262.0, 231.5]}, {'label': 'stop_level', 'grid': [199.625, 227.0, 235.25, 213.625, 209.5, 225.25, 244.0, 289.75, 251.0, 232.875, None, None, 271.5, 282.5, 293.0, 309.25, 149.0, None, None, 240.25, 253.0, 286.25, 296.5, 311.25, None, None, None, 245.75, 263.75, 290.0, 300.75, 311.25, 244.625, None, None, 263.25, 284.25, 294.75, 304.25, 292.75, 186.0, 223.5, 241.0, 268.0, 286.75, 297.5, 295.5, 273.5, 190.5, 226.5, 249.0, 266.75, 288.0, 296.5, 277.25, 248.25, 55.5, 228.5, 250.5, 271.5, 288.75, 298.5, 261.0, 231.25]}, {'label': 'stop_level', 'grid': [203.5, 225.25, 236.0, 211.5, 210.5, 225.75, 245.75, 291.5, 253.0, 244.0, None, None, 273.5, 283.75, 292.875, 310.0, 154.75, None, None, 243.5, 263.0, 287.25, 297.75, 312.0, 155.5, None, None, 244.25, 264.25, 290.25, 301.375, 312.5, 249.25, None, None, 267.0, 286.25, 295.875, 305.75, 293.75, 192.125, 228.75, 244.0, 269.75, 287.75, 298.25, 298.75, 275.25, 193.625, 227.125, 249.625, 268.375, 289.25, 297.75, 278.0, 249.5, 49.75, 228.875, 250.625, 273.5, 291.0, 300.75, 261.0, 230.25]}, {'label': 'stop_level', 'grid': [190.0, 214.625, 230.625, 219.0, 211.125, 226.5, 246.25, 292.0, 253.0, 265.375, None, None, 279.375, 284.625, 293.5, 309.5, 248.625, None, None, None, 276.375, 289.875, 299.0, 312.75, 190.0, 136.5, None, 254.625, 268.875, 288.875, 302.5, 313.25, 131.0, 106.875, None, 260.75, 286.5, 297.0, 306.5, 294.875, 191.75, 230.625, 254.25, 272.375, 290.625, 300.25, 299.25, 275.25, 214.875, 228.375, 252.375, 270.125, 289.875, 298.75, 278.75, 249.75, 45.625, 229.875, 252.125, 273.875, 292.25, 300.5, 261.5, 232.5]}, {'label': 'stop_level', 'grid': [202.25, 239.75, 242.0, 224.5, 212.5, 226.25, 245.75, 291.375, 261.0, None, None, None, 279.0, 284.375, 293.125, 310.0, 228.625, None, None, 253.0, 264.25, 287.125, 299.25, 312.375, 193.0, 136.25, None, 260.75, 275.75, 291.0, 302.25, 312.75, 118.375, 127.5, None, 269.5, 289.75, 296.875, 307.0, 294.75, 185.875, 229.75, 249.125, 270.75, 289.25, 299.25, 299.0, 276.0, 214.0, 227.875, 250.75, 269.375, 290.375, 298.75, 279.0, 248.75, 49.125, 229.25, 252.125, 275.375, 292.25, 301.5, 262.25, 231.75]}, {'label': 'no_cup', 'grid': [188.5, 196.75, 203.75, 206.375, 210.125, 225.375, 246.125, 293.25, 185.125, None, None, None, None, 284.75, 294.25, 309.375, 185.25, 197.75, None, None, 277.0, 288.375, 298.875, 312.375, 172.875, 179.375, None, None, 278.875, 291.625, 302.625, 312.75, 116.0, 111.125, None, None, 285.5, 297.125, 306.75, 295.75, 181.875, 209.875, 235.875, 264.5, 289.875, 300.25, 300.625, 275.5, 192.125, 227.25, 249.875, 269.0, 290.75, 299.625, 279.625, 249.375, 47.375, 230.125, 251.75, 274.5, 292.5, 301.875, 261.875, 231.625]}, {'label': 'no_cup', 'grid': [189.125, 196.0, 204.125, 206.625, 210.5, 225.875, 245.625, 293.0, 184.0, None, None, None, None, 284.375, 293.75, 310.25, 184.75, 198.0, None, None, 278.5, 288.625, 299.5, 312.0, 173.0, 178.75, None, None, 279.125, 291.875, 303.125, 313.875, 114.75, 116.625, None, None, 286.125, 297.5, 307.375, 296.5, 182.75, 210.375, 237.125, 266.25, 289.5, 299.5, 300.25, 276.0, 214.75, 227.375, 250.5, 269.75, 290.5, 299.125, 279.75, 249.75, 47.25, 229.125, 251.75, 277.125, 292.25, 301.375, 262.25, 232.5]}, {'label': 'no_cup', 'grid': [188.875, 196.375, 203.625, 206.375, 209.5, 226.0, 246.125, 293.25, 185.875, None, None, None, None, 284.75, 294.0, 311.0, 184.125, 197.125, None, None, 278.25, 288.375, 299.0, 313.25, 173.625, 178.625, None, None, 279.0, 291.375, 302.25, 313.5, 116.75, 111.625, None, None, 286.0, 297.0, 307.125, 295.875, 183.25, 210.625, 236.625, 264.625, 289.375, 299.0, 300.25, 275.5, 195.25, 227.875, 250.125, 270.25, 290.25, 299.75, 280.0, 249.5, 46.0, 230.375, 251.625, 274.25, 292.5, 301.75, 262.0, 232.375]}]
def read_frame(sensor):
    deadline = monotonic() + 3
    while not sensor.check_data_ready():
        if monotonic() > deadline:
            raise RuntimeError('No fresh sensor frame for 3 seconds.')
        sleep(.005)
    result = sensor.get_ranging_data()
    arrays = {}
    for name in FIELDS:
        value = getattr(result, name, None)
        if value is not None:
            # Preserve the driver values, including invalid readings and status codes.
            arrays[name] = [int(x) for x in value]
    for name in FIELDS[:3]:
        if name not in arrays or len(arrays[name]) != 64:
            raise RuntimeError(f'Expected 64 entries for {name}; got {len(arrays.get(name, []))}.')
    return {'monotonic_seconds': monotonic(), 'driver_arrays': arrays}

LABELS = ('no_cup','empty_cup','low_water','middle_water','stop_level')

def summarize(frames):
    grid=[]
    for z in range(64):
        values=[f['driver_arrays']['distance_mm'][z]/4 for f in frames
                if f['driver_arrays']['nb_target_detected'][z]>0
                and f['driver_arrays']['target_status'][z] in (5,6,9,12)]
        grid.append(median(values) if len(values)>=.6*len(frames) else None)
    return grid

# Give changed zones more weight, but retain every zone in comparisons.
background=[e['grid'] for e in EXAMPLES if e['label']=='no_cup']
weights=[]
for z in range(64):
    bg=[g[z] for g in background if g[z] is not None]
    changed=any((e['grid'][z] is not None) != (len(bg)>=3) or
                (e['grid'][z] is not None and bg and
                 min(abs(e['grid'][z]-b) for b in bg)>10)
                for e in EXAMPLES if e['label']!='no_cup')
    weights.append(2.0 if changed else 1.0)

def match(a,b):
    best=1.0
    for dy in (-1,0,1):
        for dx in (-1,0,1):
            total=denom=0.0
            overlap=0
            for row in range(8):
                for col in range(8):
                    y,x=row+dy,col+dx
                    if not (0<=y<8 and 0<=x<8):
                        continue
                    i,j=row*8+col,y*8+x
                    u,v=a[i],b[j]
                    weight=max(weights[i],weights[j])
                    denom+=weight
                    if u is None and v is None:
                        loss=0.15
                    elif u is None or v is None:
                        loss=0.8
                    else:
                        overlap+=1
                        loss=min(abs(u-v)/30.0,1.0)
                    total+=weight*loss
            if overlap>=12:
                best=min(best,total/denom+.025*(abs(dx)+abs(dy)))
    return best

def predict(grid, examples=EXAMPLES):
    if sum(x is not None for x in grid)<12:
        return 'unknown',{}
    scores={label:min(match(grid,e['grid']) for e in examples if e['label']==label)
            for label in LABELS}
    ordered=sorted(scores,key=scores.get)
    first,second=ordered[:2]
    # Experimental rejection rules, not calibrated probabilities.
    if scores[first]>.30 or scores[second]-scores[first]<.035:
        return 'unknown',scores
    return first,scores

def capture(sensor):
    sleep(2)
    for _ in range(5): read_frame(sensor)
    frames=[read_frame(sensor) for _ in range(30)]
    return summarize(frames),frames

def main():
    import qwiic_vl53l5cx
    print('FULL-GRID EXPERIMENT — NO PUMP CONTROL')
    print('Uses all 26 captures. Compares 8x8 patterns with small shifts.')
    print('This is pattern matching, not verified cup localization or overflow protection.')
    print('Stop other sensor/dispenser programs. Keep the sensor mounting fixed.')
    sensor=qwiic_vl53l5cx.QwiicVL53L5CX()
    try:
        if not sensor.is_connected() or not sensor.begin():
            raise RuntimeError('Sensor connection/initialization failed.')
        sensor.set_resolution(64)
        sensor.set_ranging_frequency_hz(10)
        sensor.start_ranging()
        while True:
            choice=input('\n1 Live view | 2 Fresh validation | q Quit: ').strip().lower()
            if choice=='q': return
            if choice=='1':
                print('Ctrl+C returns to menu. UNKNOWN means no clear match.')
                try:
                    while True:
                        grid=summarize([read_frame(sensor) for _ in range(10)])
                        label,scores=predict(grid)
                        print(label.upper(),'| valid zones',sum(x is not None for x in grid),
                              '| pattern distances', {k:round(v,3) for k,v in scores.items()},flush=True)
                except KeyboardInterrupt:
                    print('Live view stopped.')
            elif choice=='2':
                path=Path(__file__).with_name('cup_grid_validation_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.json')
                results=[]
                stages=(('no_cup','Remove the cup'),('empty_cup','Use an EMPTY cup'),
                        ('low_water','Fill about one-quarter full'),
                        ('middle_water','Fill about halfway full'),
                        ('stop_level','Fill to your chosen almost-full stop mark'))
                for label,instruction in stages:
                    print('\n'+instruction)
                    for trial in range(3):
                        while True:
                            input(f'Trial {trial+1}/3: '+('keep cup removed' if label=='no_cup' else
                                  'lift and replace cup naturally, let water settle')+'. Hands away; Enter: ')
                            grid,frames=capture(sensor)
                            predicted,scores=predict(grid)
                            print('Expected:',label,'Predicted:',predicted)
                            record=dict(expected=label,predicted=predicted,scores=scores,
                                        grid=grid,frames=frames,included=True)
                            results.append(record)
                            path.write_text(json.dumps(results,allow_nan=False))
                            answer=input('Enter keep | r redo mistake | q save and quit: ').strip().lower()
                            if answer=='r':
                                record['included']=False
                                path.write_text(json.dumps(results,allow_nan=False))
                                continue
                            if answer=='q':
                                print('Saved:',path); return
                            break
                kept=[r for r in results if r['included']]
                correct=sum(r['expected']==r['predicted'] for r in kept)
                print(f'{correct}/{len(kept)} matched. Saved: {path}')
                print('Report all misses/UNKNOWNs; this does not authorize pump control.')
    finally:
        try: sensor.stop_ranging()
        except Exception: pass

if __name__=='__main__':
    try: main()
    except KeyboardInterrupt: print('Stopped; previously saved captures remain.')
    except (RuntimeError,ImportError,OSError) as error: print('Stopped:',error)
