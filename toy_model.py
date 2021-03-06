# CLimate Analysis using Digital Estimations (CLAuDE)

import numpy as np
import matplotlib.pyplot as plt
import time
import sys
import pickle
import claude_low_level_library as low_level
import claude_top_level_library as top_level
# from twitch import prime_sub

from config import Config


temperature_world = np.zeros((Config.NLAT, Config.NLON))

if not Config.LOAD:
    # initialise arrays for various physical fields
    temperature_world += 290
    potential_temperature = np.zeros((Config.NLAT, Config.NLON, Config.NLEVELS))
    u = np.zeros_like(potential_temperature)
    v = np.zeros_like(potential_temperature)
    w = np.zeros_like(potential_temperature)
    atmosp_addition = np.zeros_like(potential_temperature)

    # read temperature and density in from standard atmosphere
    with open("standard_atmosphere.txt", "r") as f:
        standard_temp = []
        standard_pressure = []

        standard_temp_append = standard_temp.append
        standard_pressure_append = standard_pressure.append

        # These var names hurt my soul.
        for x in f:
            h, t, r, p = x.split()
            standard_temp_append(float(t))
            standard_pressure_append(float(p))

    # density_profile = np.interp(
    # x=heights/1E3,xp=standard_height,fp=standard_density)
    temp_profile = np.interp(
        x=Config.PRESSURE_LEVELS[::-1],
        xp=standard_pressure[::-1],
        fp=standard_temp[::-1]
    )[::-1]
    for k in range(Config.NLEVELS):
        potential_temperature[:, :, k] = temp_profile[k]

    potential_temperature = low_level.t_to_theta(
        potential_temperature,
        Config.PRESSURE_LEVELS
    )
    geopotential = np.zeros_like(potential_temperature)

if Config.INITIAL_SETUP:
    sigma = np.zeros_like(Config.PRESSURE_LEVELS)
    kappa = 287 / 1000
    # pride
    for index in range(len(sigma)):
        sigma[index] = 1E3 * (
            Config.PRESSURE_LEVELS[index] / Config.PRESSURE_LEVELS[0]
        ) ** kappa

    heat_capacity_earth = np.zeros_like(temperature_world) + 1E6

    # heat_capacity_earth[15:36,30:60] = 1E7
    # heat_capacity_earth[30:40,80:90] = 1E7

    albedo_variance = 0.001
    albedo = np.random.uniform(
        -albedo_variance,
        albedo_variance, (Config.NLAT, Config.NLON)
    ) + 0.2
    albedo = np.zeros((Config.NLAT, Config.NLON)) + 0.2

    specific_gas = 287
    thermal_diffusivity_roc = 1.5E-6

    # define planet size and various geometric constants
    circumference = 2 * np.pi * Config.PLANET_RADIUS
    circle = np.pi * Config.PLANET_RADIUS ** 2
    sphere = 4 * np.pi * Config.PLANET_RADIUS ** 2

    # define how far apart the gridpoints are: note that we use central
    # difference derivatives, and so these distances are actually twice the
    # distance between gridboxes
    dy = circumference / Config.NLAT
    dx = np.zeros(Config.NLAT)
    coriolis = np.zeros(Config.NLAT)  # also define the coriolis parameter here
    angular_speed = 2 * np.pi / Config.DAY
    for index in range(Config.NLAT):
        dx[index] = dy * np.cos(Config.LAT[index] * np.pi / 180)
        coriolis[index] = angular_speed * np.sin(Config.LAT[index] * np.pi / 180)

if Config.SETUP_GRIDS:
    grid_pad = 2

    pole_low_index_S = np.where(Config.LAT > Config.POLE_LOWER_LAT_LIMIT)[0][0]
    pole_high_index_S = np.where(Config.LAT > Config.POLE_HIGHER_LAT_LIMIT)[0][0]

    # initialise grid
    polar_grid_resolution = dx[pole_low_index_S]
    size_of_grid = Config.PLANET_RADIUS * np.cos(
        Config.LAT[pole_low_index_S + grid_pad] * np.pi / 180.0
    )

    def get_grid():
        return np.arange(-size_of_grid, size_of_grid, polar_grid_resolution)

    """
    south Config.POLE
    """
    grid_x_values_S = get_grid()
    grid_y_values_S = get_grid()
    grid_xx_S, grid_yy_S = np.meshgrid(grid_x_values_S, grid_y_values_S)

    grid_side_length = len(grid_x_values_S)

    grid_lat_coords_S = (
        -np.arccos(
            ((grid_xx_S ** 2 + grid_yy_S ** 2) ** 0.5) / Config.PLANET_RADIUS
        ) * 180.0 / np.pi
    ).flatten()
    grid_lon_coords_S = (
        180.0 - np.arctan2(grid_yy_S, grid_xx_S) * 180.0 / np.pi
    ).flatten()

    polar_x_coords_S = []
    polar_y_coords_S = []
    for index in range(pole_low_index_S):
        for j in range(Config.NLON):
            var = Config.PLANET_RADIUS * np.cos(Config.LAT[index] * np.pi / 180.0)
            polar_x_coords_S.append(
                var * np.sin(Config.LON[j] * np.pi / 180.0)
            )
            polar_y_coords_S.append(
                -var * np.cos(Config.LON[j] * np.pi / 180.0)
            )

    """
    north Config.POLE
    """
    pole_low_index_N = np.where(Config.LAT < -Config.POLE_LOWER_LAT_LIMIT)[0][-1]
    pole_high_index_N = np.where(Config.LAT < -Config.POLE_HIGHER_LAT_LIMIT)[0][-1]

    grid_x_values_N = get_grid()
    grid_y_values_N = get_grid()
    grid_xx_N, grid_yy_N = np.meshgrid(grid_x_values_N, grid_y_values_N)

    grid_lat_coords_N = (
        np.arccos((grid_xx_N ** 2 + grid_yy_N ** 2) ** 0.5 / Config.PLANET_RADIUS)
        * 180.0 / np.pi
    ).flatten()
    grid_lon_coords_N = (
        180.0 - np.arctan2(grid_yy_N, grid_xx_N) * 180.0 / np.pi
    ).flatten()

    polar_x_coords_N = []
    polar_y_coords_N = []
    for index in np.arange(pole_low_index_N, Config.NLAT):
        for j in range(Config.NLON):
            var = Config.PLANET_RADIUS*np.cos(Config.LAT[index]*np.pi/180.0)
            polar_x_coords_N.append(var * np.sin(Config.LON[j] * np.pi / 180.0))
            polar_y_coords_N.append(-var * np.cos(Config.LON[j] * np.pi / 180.0))

    indices = (
        pole_low_index_N,
        pole_high_index_N,
        pole_low_index_S,
        pole_high_index_S
    )
    grids = (
        grid_xx_N.shape[0],
        grid_xx_S.shape[0]
    )

    # create Coriolis data on north and south planes
    data = np.zeros((Config.NLAT-pole_low_index_N + grid_pad, Config.NLON))
    for index in np.arange(pole_low_index_N - grid_pad, Config.NLAT):
        data[index - pole_low_index_N, :] = coriolis[index]

    coriolis_plane_N = low_level.beam_me_up_2D(
        Config.LAT[(pole_low_index_N-grid_pad):],
        Config.LON,
        data,
        grids[0],
        grid_lat_coords_N,
        grid_lon_coords_N
    )

    data = np.zeros((pole_low_index_S + grid_pad, Config.NLON))
    for index in range(pole_low_index_S+grid_pad):
        data[index, :] = coriolis[index]

    coriolis_plane_S = low_level.beam_me_up_2D(
        Config.LAT[:(pole_low_index_S+grid_pad)],
        Config.LON,
        data,
        grids[1],
        grid_lat_coords_S,
        grid_lon_coords_S
    )

    x_dot_N = np.zeros((grids[0], grids[0], Config.NLEVELS))
    y_dot_N = np.zeros((grids[0], grids[0], Config.NLEVELS))
    x_dot_S = np.zeros((grids[1], grids[1], Config.NLEVELS))
    y_dot_S = np.zeros((grids[1], grids[1], Config.NLEVELS))

    coords = (grid_lat_coords_N, grid_lon_coords_N, grid_x_values_N,
              grid_y_values_N, polar_x_coords_N, polar_y_coords_N,
              grid_lat_coords_S, grid_lon_coords_S, grid_x_values_S,
              grid_y_values_S, polar_x_coords_S, polar_y_coords_S)

"""
LINE BREAK
"""

# INITIATE TIME
t = 0.0

# NOTE
# how potential_temperature is defined could result in it being out of bounds.

if Config.LOAD:
    # Config.LOAD in previous Config.SAVE file
    (potential_temperature, temperature_world, u, v,
     w, x_dot_N, y_dot_N, x_dot_S, y_dot_S, t, albedo, tracer
     ) = pickle.load(open(Config.SAVE_FILE, "rb"))

sample_level = 5
tracer = np.zeros_like(potential_temperature)

last_plot = t - 0.1
last_save = t - 0.1

if Config.PLOT:
    if not Config.DIAGNOSTIC:
        # set up Config.PLOT
        f, ax = plt.subplots(2, figsize=(9, 9))
        f.canvas.set_window_title('CLAuDE')
        ax[0].contourf(Config.LON_PLOT, Config.LAT_PLOT, temperature_world, cmap="seismic")
        ax[0].streamplot(
            Config.LON_PLOT,
            Config.LAT_PLOT,
            u[:, :, 0],
            v[:, :, 0],
            color="white",
            density=1
        )
        test = ax[1].contourf(
            Config.HEIGHTS_PLOT,
            Config.LAT_Z_PLOT,
            np.transpose(
                np.mean(
                    low_level.theta_to_t(
                        potential_temperature, Config.PRESSURE_LEVELS
                    ), axis=1
                )
            )[:Config.TOP, :],
            cmap="seismic",
            levels=15
        )
        ax[1].contour(
            Config.HEIGHTS_PLOT,
            Config.LAT_Z_PLOT,
            np.transpose(
                np.mean(
                    u,
                    axis=1
                )
            )[:Config.TOP, :],
            colors="white",
            levels=20,
            linewidths=1,
            alpha=0.8
        )
        ax[1].quiver(
            Config.HEIGHTS_PLOT,
            Config.LAT_Z_PLOT,
            np.transpose(
                np.mean(
                    v,
                    axis=1
                )
            )[:Config.TOP, :],
            np.transpose(
                np.mean(
                    10 * w,
                    axis=1
                )
            )[:Config.TOP, :],
            color="black"
        )
        plt.subplots_adjust(left=0.1, right=0.75)
        ax[0].set_title("Surface temperature")
        ax[0].set_xlim(Config.LON.min(), Config.LON.max())
        ax[1].set_title("Atmosphere temperature")
        ax[1].set_xlim(Config.LAT.min(), Config.LAT.max())
        ax[1].set_ylim((
            Config.PRESSURE_LEVELS.max() / 100,
            Config.PRESSURE_LEVELS[:Config.TOP].min() / 100
        ))
        ax[1].set_yscale("log")
        ax[1].set_ylabel("Pressure (hPa)")
        ax[1].set_xlabel("Latitude")
        cbar_ax = f.add_axes([0.85, 0.15, 0.05, 0.7])
        f.colorbar(test, cax=cbar_ax)
        cbar_ax.set_title("Temperature (K)")
    else:
        # set up Config.PLOT
        f, ax = plt.subplots(2, 2, figsize=(9, 9))
        f.canvas.set_window_title("CLAuDE")
        ax[0, 0].contourf(
            Config.HEIGHTS_PLOT,
            Config.LAT_Z_PLOT,
            np.transpose(np.mean(u, axis=1))[:Config.TOP, :],
            cmap="seismic"
        )

        ax[0, 0].set_title("u")
        ax[0, 1].contourf(
            Config.HEIGHTS_PLOT,
            Config.LAT_Z_PLOT,
            np.transpose(np.mean(v, axis=1))[:Config.TOP, :],
            cmap="seismic"
        )
        ax[0, 1].set_title("v")
        ax[1, 0].contourf(
            Config.HEIGHTS_PLOT,
            Config.LAT_Z_PLOT,
            np.transpose(
                np.mean(w, axis=1)
            )[:Config.TOP, :],
            cmap="seismic"
        )
        ax[1, 0].set_title("w")
        ax[1, 1].contourf(
            Config.HEIGHTS_PLOT,
            Config.LAT_Z_PLOT,
            np.transpose(
                np.mean(atmosp_addition, axis=1)
            )[:Config.TOP, :],
            cmap="seismic"
        )
        ax[1, 1].set_title("atmosp_addition")

        for axis in ax.ravel():
            axis.set_ylim((
                Config.PRESSURE_LEVELS.max() / 100, Config.PRESSURE_LEVELS[:Config.TOP].min() / 100
            ))
            axis.set_yscale("log")

    f.suptitle("Time {} days".format(round(t / Config.DAY, 2)))

    if Config.LEVEL_PLOTS:
        level_divisions = int(np.floor(Config.NLEVELS/Config.NPLOTS))
        level_plots_levels = range(Config.NLEVELS)[::level_divisions][::-1]

        g, bx = plt.subplots(Config.NPLOTS, figsize=(9, 8), sharex=True)
        g.canvas.set_window_title('CLAuDE pressure levels')
        for k, z in zip(range(Config.NPLOTS), level_plots_levels):
            z += 1
            bx[k].contourf(
                Config.LON_PLOT,
                Config.LAT_PLOT,
                potential_temperature[:, :, z],
                cmap="seismic"
            )
            bx[k].set_title(str(Config.PRESSURE_LEVELS[z] / 100) + " hPa")
            bx[k].set_ylabel("Latitude")

        bx[-1].set_xlabel("Longitude")

    plt.ion()
    plt.show()
    plt.pause(2)

    if not Config.DIAGNOSTIC:
        ax[0].cla()
        ax[1].cla()

        if Config.LEVEL_PLOTS:
            for k in range(Config.NPLOTS):
                bx[k].cla()
    else:
        ax[0, 0].cla()
        ax[0, 1].cla()
        ax[1, 0].cla()
        ax[1, 1].cla()

if Config.ABOVE:
    g, gx = plt.subplots(1, 3, figsize=(15, 5))
    plt.ion()
    plt.show()


def plotting_routine():
    quiver_padding = int(12 / Config.RESOLUTION)

    if Config.PLOT:
        if Config.VERBOSE:
            before_plot = time.time()

        # update Config.PLOT
        if not Config.DIAGNOSTIC:
            # ax[0].contourf(Config.LON_PLOT, Config.LAT_PLOT, temperature_world,
            # cmap='seismic',levels=15)

            # field = np.copy(w)[:,:,sample_level]
            field = np.copy(atmosp_addition)[:, :, sample_level]
            ax[0].contourf(
                Config.LON_PLOT,
                Config.LAT_PLOT,
                field,
                cmap="seismic",
                levels=15
            )
            ax[0].contour(
                Config.LON_PLOT,
                Config.LAT_PLOT,
                tracer[:, :, sample_level],
                alpha=0.5,
                antialiased=True,
                levels=np.arange(0.01, 1.01, 0.01)
            )

            if velocity:
                ax[0].quiver(
                    Config.LON_PLOT[::quiver_padding, ::quiver_padding],
                    Config.LAT_PLOT[::quiver_padding, ::quiver_padding],
                    u[::quiver_padding, ::quiver_padding, sample_level],
                    v[::quiver_padding, ::quiver_padding, sample_level],
                    color="white"
                )

            # ax[0].set_title('$\it{Ground} \quad \it{temperature}$')

            ax[0].set_xlim((Config.LON.min(), Config.LON.max()))
            ax[0].set_ylim((Config.LAT.min(), Config.LAT.max()))
            ax[0].set_ylabel("Latitude")
            ax[0].axhline(y=0, color="black", alpha=0.3)
            ax[0].set_xlabel("Longitude")

            test = ax[1].contourf(Config.HEIGHTS_PLOT, Config.LAT_Z_PLOT, np.transpose(
                np.mean(
                    low_level.theta_to_t(
                        potential_temperature,
                        Config.PRESSURE_LEVELS
                    ),
                    axis=1
                ))[:Config.TOP, :],
                cmap="seismic",
                levels=15
            )

            # test = ax[1].contourf(Config.HEIGHTS_PLOT, Config.LAT_Z_PLOT, np.transpose(np.
            # mean(atmosp_addition,axis=1))[:Config.TOP,:], cmap='seismic',levels=15)
            # test = ax[1].contourf(Config.HEIGHTS_PLOT, Config.LAT_Z_PLOT, np.transpose(np.
            # mean(potential_temperature,axis=1)), cmap='seismic',levels=15)
            ax[1].contour(
                Config.HEIGHTS_PLOT,
                Config.LAT_Z_PLOT,
                np.transpose(
                    np.mean(tracer, axis=1)
                )[:Config.TOP, :],
                alpha=0.5,
                antialiased=True,
                levels=np.arange(0.001, 1.01, 0.01)
                )

            if velocity:
                ax[1].contour(
                    Config.HEIGHTS_PLOT,
                    Config.LAT_Z_PLOT,
                    np.transpose(
                        np.mean(u, axis=1)
                    )[:Config.TOP, :],
                    colors="white",
                    levels=20,
                    linewidths=1,
                    alpha=0.8
                )
                ax[1].quiver(
                    Config.HEIGHTS_PLOT,
                    Config.LAT_Z_PLOT,
                    np.transpose(
                        np.mean(v, axis=1)
                    )[:Config.TOP, :],
                    np.transpose(np.mean(5 * w, axis=1))[:Config.TOP, :],
                    color="black"
                )

            ax[1].set_title("$\it{Atmospheric} \quad \it{temperature}$")
            ax[1].set_xlim((-90, 90))
            ax[1].set_ylim((
                Config.PRESSURE_LEVELS.max() / 100,
                Config.PRESSURE_LEVELS[:Config.TOP].min() / 100)
            )
            ax[1].set_ylabel("Pressure (hPa)")
            ax[1].set_xlabel("Latitude")
            ax[1].set_yscale("log")
            f.colorbar(test, cax=cbar_ax)
            cbar_ax.set_title('Temperature (K)')
        else:
            ax[0, 0].contourf(
                Config.HEIGHTS_PLOT,
                Config.LAT_Z_PLOT,
                np.transpose(
                    np.mean(u, axis=1)
                )[:Config.TOP, :],
                cmap="seismic"
            )
            ax[0, 0].set_title("u")
            ax[0, 1].contourf(
                Config.HEIGHTS_PLOT,
                Config.LAT_Z_PLOT,
                np.transpose(
                    np.mean(v, axis=1)
                )[:Config.TOP, :],
                cmap="seismic"
            )
            ax[0, 1].set_title("v")
            ax[1, 0].contourf(
                Config.HEIGHTS_PLOT,
                Config.LAT_Z_PLOT,
                np.transpose(
                    np.mean(w, axis=1)
                )[:Config.TOP, :],
                cmap="seismic"
            )
            ax[1, 0].set_title("w")
            ax[1, 1].contourf(
                Config.HEIGHTS_PLOT,
                Config.LAT_Z_PLOT,
                np.transpose(
                    np.mean(atmosp_addition, axis=1)
                )[:Config.TOP, :],
                cmap="seismic"
            )
            ax[1, 1].set_title("atmosp_addition")

            for axis in ax.ravel():
                axis.set_ylim((
                    Config.PRESSURE_LEVELS.max() / 100,
                    Config.PRESSURE_LEVELS[:Config.TOP].min() / 100
                ))
                axis.set_yscale("log")

        f.suptitle("Time {} days".format(round(t / Config.DAY, 2)))

        if Config.LEVEL_PLOTS:
            for k, z in zip(range(Config.NPLOTS), level_plots_levels):	
                z += 1
                bx[k].contourf(
                    Config.LON_PLOT,
                    Config.LAT_PLOT,
                    potential_temperature[:, :, z],
                    cmap="seismic",
                    levels=15
                )
                bx[k].quiver(
                    Config.LON_PLOT[::quiver_padding, ::quiver_padding],
                    Config.LAT_PLOT[::quiver_padding, ::quiver_padding],
                    u[::quiver_padding, ::quiver_padding, z],
                    v[::quiver_padding, ::quiver_padding, z],
                    color="white"
                )
                bx[k].set_title(str(round(Config.PRESSURE_LEVELS[z] / 100)) + " hPa")
                bx[k].set_ylabel("Latitude")
                bx[k].set_xlim((Config.LON.min(), Config.LON.max()))
                bx[k].set_ylim((Config.LAT.min(), Config.LAT.max()))

            bx[-1].set_xlabel("Longitude")

    if Config.ABOVE and velocity:
        gx[0].set_title("Original data")
        gx[1].set_title("Polar plane")
        gx[2].set_title("Reprojected data")

        g.suptitle("Time {} days".format(round(t / Config.DAY, 2)))

        gx[0].set_title("temperature")

        if Config.POLE.lower() == 's':
            gx[0].contourf(
                Config.LON,
                Config.LAT[:pole_low_index_S],
                potential_temperature[:pole_low_index_S, :, Config.ABOVE_LEVEL]
            )

            gx[1].set_title("polar_plane_advect")
            polar_temps = low_level.beam_me_up(
                Config.LAT[:pole_low_index_S],
                Config.LON,
                potential_temperature[:pole_low_index_S, :, :],
                grids[1],
                grid_lat_coords_S,
                grid_lon_coords_S
            )
            output = low_level.beam_me_up(
                Config.LAT[:pole_low_index_S],
                Config.LON,
                south_reprojected_addition,
                grids[1],
                grid_lat_coords_S,
                grid_lon_coords_S
            )

            gx[1].contourf(
                grid_x_values_S / 1E3,
                grid_y_values_S / 1E3,
                output[:, :, Config.ABOVE_LEVEL]
            )
            gx[1].contour(
                grid_x_values_S / 1E3,
                grid_y_values_S / 1E3,
                polar_temps[:, :, Config.ABOVE_LEVEL],
                colors="white",
                levels=20,
                linewidths=1,
                alpha=0.8
            )
            gx[1].quiver(
                grid_x_values_S / 1E3, grid_y_values_S / 1E3,
                x_dot_S[:, :, Config.ABOVE_LEVEL],
                y_dot_S[:, :, Config.ABOVE_LEVEL]
            )

            gx[1].add_patch(
                plt.Circle(
                    (0, 0),
                    Config.PLANET_RADIUS * np.cos(
                        Config.LAT[pole_low_index_S] * np.pi / 180.0
                    ) / 1E3,
                    color="r",
                    fill=False
                )
            )
            gx[1].add_patch(
                plt.Circle(
                    (0, 0),
                    Config.PLANET_RADIUS * np.cos(
                        Config.LAT[pole_high_index_S] * np.pi / 180.0
                    ) / 1E3,
                    color="r",
                    fill=False
                )
            )

            gx[2].set_title("south_addition_smoothed")
            gx[2].contourf(
                Config.LON,
                Config.LAT[:pole_low_index_S],
                south_addition_smoothed[:pole_low_index_S, :, Config.ABOVE_LEVEL]
            )
            # gx[2].contourf(Config.LON,Config.LAT[:pole_low_index_S],u[:pole_low_index_S,:,Config.ABOVE_LEVEL])
            gx[2].quiver(
                Config.LON[::5],
                Config.LAT[:pole_low_index_S],
                u[:pole_low_index_S, ::5, Config.ABOVE_LEVEL],
                v[:pole_low_index_S, ::5, Config.ABOVE_LEVEL]
            )
        else:
            gx[0].contourf(
                Config.LON,
                Config.LAT[pole_low_index_N:],
                potential_temperature[pole_low_index_N:, :, Config.ABOVE_LEVEL]
            )

            gx[1].set_title("polar_plane_advect")
            polar_temps = low_level.beam_me_up(
                Config.LAT[pole_low_index_N:],
                Config.LON,
                np.flip(
                    potential_temperature[pole_low_index_N:, :, :],
                    axis=1
                ),
                grids[0],
                grid_lat_coords_N,
                grid_lon_coords_N
            )
            output = low_level.beam_me_up(
                Config.LAT[pole_low_index_N:],
                Config.LON,
                north_reprojected_addition,
                grids[0],
                grid_lat_coords_N,
                grid_lon_coords_N
            )
            gx[1].contourf(
                grid_x_values_N / 1E3,
                grid_y_values_N / 1E3,
                output[:, :, Config.ABOVE_LEVEL]
            )
            gx[1].contour(
                grid_x_values_N / 1E3,
                grid_y_values_N / 1E3,
                polar_temps[:, :, Config.ABOVE_LEVEL],
                colors="white",
                levels=20,
                linewidths=1,
                alpha=0.8
            )
            gx[1].quiver(
                grid_x_values_N / 1E3,
                grid_y_values_N / 1E3,
                x_dot_N[:, :, Config.ABOVE_LEVEL],
                y_dot_N[:, :, Config.ABOVE_LEVEL]
            )

            gx[1].add_patch(
                plt.Circle(
                    (0, 0),
                    Config.PLANET_RADIUS * np.cos(
                        Config.LAT[pole_low_index_N] * np.pi / 180.0
                    ) / 1E3,
                    color="r",
                    fill=False
                )
            )
            gx[1].add_patch(
                plt.Circle(
                    (0, 0),
                    Config.PLANET_RADIUS * np.cos(
                        Config.LAT[pole_high_index_N] * np.pi / 180.0
                    ) / 1E3,
                    color="r",
                    fill=False
                )
            )

            gx[2].set_title("south_addition_smoothed")
            # gx[2].contourf(Config.LON,Config.LAT[pole_low_index_N:],north_addition_smoothed[:,:,Config.ABOVE_LEVEL])
            gx[2].contourf(
                Config.LON,
                Config.LAT[pole_low_index_N:],
                u[pole_low_index_N:, :, Config.ABOVE_LEVEL]
            )
            gx[2].quiver(
                Config.LON[::5], Config.LAT[pole_low_index_N:],
                u[pole_low_index_N:, ::5, Config.ABOVE_LEVEL],
                v[pole_low_index_N:, ::5, Config.ABOVE_LEVEL]
            )

    # clear plots
    if Config.PLOT or Config.ABOVE:
        plt.pause(0.001)

    if Config.PLOT:
        if not Config.DIAGNOSTIC:
            ax[0].cla()
            ax[1].cla()
            cbar_ax.cla()  
        else:
            ax[0, 0].cla()
            ax[0, 1].cla()
            ax[1, 0].cla()
            ax[1, 1].cla()

        if Config.LEVEL_PLOTS:
            for k in range(Config.NPLOTS):
                bx[k].cla()

        if Config.VERBOSE:
            time_taken = float(round(time.time() - before_plot, 3))
            print('Plotting: ', str(time_taken), 's')

    if Config.ABOVE:
        gx[0].cla()
        gx[1].cla()
        gx[2].cla()


while True:
    initial_time = time.time()

    if t < Config.SPINUP_LENGTH:
        dt = Config.DT_SPINUP
        velocity = False
    else:
        dt = Config.DT_MAIN
        velocity = True

    # print current time in simulation to command line
    print("+++ t = " + str(round(t / Config.DAY, 2)) + " days +++")
    print(
        "T:",
        round(temperature_world.max() - 273.15, 1),
        "-",
        round(temperature_world.min() - 273.15, 1),
        "C",
        sep=" "
    )
    print(
        "U:",
        round(u.max(), 2),
        "-",
        round(u.min(), 2),
        "V:",
        round(v.max(), 2),
        "-",
        round(v.min(), 2),
        "W:",
        round(w.max(), 2),
        "-",
        round(w.min(), 4),
        sep=" "
    )

    tracer[40, 50, sample_level] = 1
    tracer[20, 50, sample_level] = 1

    if Config.VERBOSE:
        before_radiation = time.time()

    temperature_world, potential_temperature = top_level.radiation_calculation(
        temperature_world,
        potential_temperature,
        Config.PRESSURE_LEVELS,
        heat_capacity_earth,
        albedo,
        Config.INSOLATION,
        Config.LAT,
        Config.LON,
        t,
        dt,
        Config.DAY,
        Config.YEAR,
        Config.AXIAL_TILT
    )

    if Config.SMOOTHING:
        potential_temperature = top_level.smoothing_3D(
            potential_temperature, Config.SMOOTHING_PARAM_T
        )

    if Config.VERBOSE:
        time_taken = float(round(time.time() - before_radiation, 3))
        print('Radiation: ', str(time_taken), 's')

    diffusion = top_level.laplacian_2d(temperature_world, dx, dy)
    diffusion[0, :] = np.mean(diffusion[1, :], axis=0)
    diffusion[-1, :] = np.mean(diffusion[-2, :], axis=0)
    temperature_world -= dt * 1E-5 * diffusion

    # update geopotential field
    geopotential = np.zeros_like(potential_temperature)
    for k in np.arange(1, Config.NLEVELS):
        geopotential[:, :, k] = (
            geopotential[:, :, k-1] - potential_temperature[:, :, k]
            * (sigma[k] - sigma[k-1])
        )

    if velocity:
        if Config.VERBOSE:
            before_velocity = time.time()

        u_add, v_add = top_level.velocity_calculation(
            u,
            v,
            w,
            Config.PRESSURE_LEVELS,
            geopotential,
            potential_temperature,
            coriolis,
            Config.GRAVITY,
            dx,
            dy,
            dt
        )

        if Config.VERBOSE:	
            time_taken = float(round(time.time() - before_velocity, 3))
            print('Velocity: ', str(time_taken), 's')

            before_projection = time.time()

        grid_velocities = (x_dot_N, y_dot_N, x_dot_S, y_dot_S)

        (u_add, v_add, north_reprojected_addition, south_reprojected_addition,
         x_dot_N, y_dot_N, x_dot_S, y_dot_S) = top_level.polar_planes(
             u,
             v,
             u_add,
             v_add,
             potential_temperature,
             geopotential,
             grid_velocities,
             indices,
             grids,
             coords,
             coriolis_plane_N,
             coriolis_plane_S,
             grid_side_length,
             Config.PRESSURE_LEVELS,
             Config.LAT,
             Config.LON,
             dt,
             polar_grid_resolution,
             Config.GRAVITY
        )

        u += u_add
        v += v_add

        if Config.SMOOTHING:
            u = top_level.smoothing_3D(u, Config.SMOOTHING_PARAM_U)
            v = top_level.smoothing_3D(v, Config.SMOOTHING_PARAM_V)

        x_dot_N, y_dot_N, x_dot_S, y_dot_S = top_level.update_plane_velocities(
            Config.LAT,
            Config.LON,
            pole_low_index_N,
            pole_low_index_S,
            np.flip(u[pole_low_index_N:, :, :], axis=1),
            np.flip(v[pole_low_index_N:, :, :], axis=1),
            grids,
            grid_lat_coords_N,
            grid_lon_coords_N,
            u[:pole_low_index_S, :, :],
            v[:pole_low_index_S, :, :],
            grid_lat_coords_S,
            grid_lon_coords_S
        )

        if Config.VERBOSE:
            time_taken = float(round(time.time() - before_projection, 3))
            print('Projection: ', str(time_taken), 's')

            # allow for thermal advection in the atmosphere
            before_advection = time.time()

            before_w = time.time()

        # using updated u,v fields calculated w
        # https://www.sjsu.edu/faculty/watkins/omega.htm
        w = top_level.w_calculation(
            u,
            v,
            w,
            Config.PRESSURE_LEVELS,
            geopotential,
            potential_temperature,
            coriolis,
            Config.GRAVITY,
            dx,
            dy,
            dt
        )

        if Config.SMOOTHING:
            w = top_level.smoothing_3D(w, Config.SMOOTHING_PARAM_W, 0.25)

        theta_N = low_level.beam_me_up(
            Config.LAT[pole_low_index_N:],
            Config.LON,
            potential_temperature[pole_low_index_N:, :, :],
            grids[0],
            grid_lat_coords_N,
            grid_lon_coords_N
        )
        w_N = top_level.w_plane(
            x_dot_N,
            y_dot_N,
            theta_N,
            Config.PRESSURE_LEVELS,
            polar_grid_resolution,
            Config.GRAVITY
        )
        w_N = np.flip(
            low_level.beam_me_down(
                Config.LON,
                w_N,
                pole_low_index_N,
                grid_x_values_N,
                grid_y_values_N,
                polar_x_coords_N,
                polar_y_coords_N
            ),
            axis=1
        )
        w[pole_low_index_N:, :, :] = low_level.combine_data(
            pole_low_index_N,
            pole_high_index_N,
            w[pole_low_index_N:, :, :],
            w_N,
            Config.LAT
        )

        w_S = top_level.w_plane(
            x_dot_S,
            y_dot_S,
            low_level.beam_me_up(
                Config.LAT[:pole_low_index_S],
                Config.LON,
                potential_temperature[:pole_low_index_S, :, :],
                grids[1],
                grid_lat_coords_S,
                grid_lon_coords_S
            ),
            Config.PRESSURE_LEVELS,
            polar_grid_resolution,
            Config.GRAVITY
        )
        w_S = low_level.beam_me_down(
            Config.LON,
            w_S,
            pole_low_index_S,
            grid_x_values_S,
            grid_y_values_S,
            polar_x_coords_S,
            polar_y_coords_S
        )
        w[:pole_low_index_S, :, :] = low_level.combine_data(
            pole_low_index_S,
            pole_high_index_S,
            w[:pole_low_index_S, :, :],
            w_S,
            Config.LAT
        )

        # for k in np.arange(1,Config.NLEVELS-1):
        # 	north_reprojected_addition[:,:,k] += 0.5*(w_N[:,:,k] + abs(w_N[:,:,
        # k]))*(potential_temperature[pole_low_index_N:,:,k] - 
        # potential_temperature[pole_low_index_N:,:,k-1])/(Config.PRESSURE_LEVELS[k] -
        # Config.PRESSURE_LEVELS[k-1])
        # 	north_reprojected_addition[:,:,k] += 0.5*(w_N[:,:,k] - abs(w_N[:,:,
        # k]))*(potential_temperature[pole_low_index_N:,:,k+1] - 
        # potential_temperature[pole_low_index_N:,:,k])/(Config.PRESSURE_LEVELS[k+1] -
        # Config.PRESSURE_LEVELS[k])

        # 	south_reprojected_addition[:,:,k] += 0.5*(w_S[:,:,k] + abs(w_S[:,:,
        # k]))*(potential_temperature[:pole_low_index_S,:,k] - 
        # potential_temperature[:pole_low_index_S,:,k-1])/(Config.PRESSURE_LEVELS[k] -
        # Config.PRESSURE_LEVELS[k-1])
        # 	south_reprojected_addition[:,:,k] += 0.5*(w_S[:,:,k] - abs(w_S[:,:,
        # k]))*(potential_temperature[:pole_low_index_S,:,k+1] - 
        # potential_temperature[:pole_low_index_S,:,k])/(Config.PRESSURE_LEVELS[k+1] -
        # Config.PRESSURE_LEVELS[k])

        w[:, :, 18:] *= 0

        if Config.VERBOSE:	
            time_taken = float(round(time.time() - before_w, 3))
            print('Calculate w: ', str(time_taken), 's')

        """
        LINE BREAK
        """

        atmosp_addition = top_level.divergence_with_scalar(
            potential_temperature,
            u,
            v,
            w,
            dx,
            dy,
            Config.PRESSURE_LEVELS
        )

        # combine addition calculated on polar grid with
        # that calculated on the cartestian grid
        north_addition_smoothed = low_level.combine_data(
            pole_low_index_N,
            pole_high_index_N,
            atmosp_addition[pole_low_index_N:, :, :],
            north_reprojected_addition,
            Config.LAT
        )
        south_addition_smoothed = low_level.combine_data(
            pole_low_index_S,
            pole_high_index_S,
            atmosp_addition[:pole_low_index_S, :, :],
            south_reprojected_addition,
            Config.LAT
        )

        # add the blended/combined addition to
        # global temperature addition array
        atmosp_addition[:pole_low_index_S, :, :] = south_addition_smoothed
        atmosp_addition[pole_low_index_N:, :, :] = north_addition_smoothed

        if Config.SMOOTHING:
            atmosp_addition = top_level.smoothing_3D(
                atmosp_addition,
                Config.SMOOTHING_PARAM_ADD
            )

        atmosp_addition[:, :, 17] *= 0.5
        atmosp_addition[:, :, 18:] *= 0

        potential_temperature -= dt*atmosp_addition

        """
        LINE BREAK
        """

        tracer_addition = top_level.divergence_with_scalar(
            tracer,
            u,
            v,
            w,
            dx,
            dy,
            Config.PRESSURE_LEVELS
        )
        tracer_addition[:4, :, :] *= 0
        tracer_addition[-4:, :, :] *= 0

        for k in np.arange(1, Config.NLEVELS-1):
            tracer_addition[:, :, k] += (
                0.5 * (w[:, :, k] - abs(w[:, :, k])) *
                (tracer[:, :, k] - tracer[:, :, k-1]) /
                (Config.PRESSURE_LEVELS[k] - Config.PRESSURE_LEVELS[k-1])
            )
            tracer_addition[:, :, k] += (
                0.5 * (w[:, :, k] + abs(w[:, :, k])) *
                (tracer[:, :, k+1] - tracer[:, :, k]) /
                (Config.PRESSURE_LEVELS[k] - Config.PRESSURE_LEVELS[k-1])
            )

        tracer -= dt*tracer_addition

        diffusion = top_level.laplacian_3d(
            potential_temperature,
            dx,
            dy,
            Config.PRESSURE_LEVELS
        )
        diffusion[0, :, :] = np.mean(diffusion[1, :, :], axis=0)
        diffusion[-1, :, :] = np.mean(diffusion[-2, :, :], axis=0)
        potential_temperature -= dt * 1E-4 * diffusion

        """
        LINE BREAK
        """

        if Config.VERBOSE:	
            time_taken = float(round(time.time() - before_advection, 3))
            print('Advection: ', str(time_taken), 's')

    if t-last_plot >= Config.PLOT_FREQ*dt:
        plotting_routine()
        last_plot = t

    if Config.SAVE and t-last_save >= Config.SAVE_FREQ * dt:
        pickle.dump((
            potential_temperature,
            temperature_world,
            u,
            v,
            w,
            x_dot_N,
            y_dot_N,
            x_dot_S,
            y_dot_S,
            t,
            albedo,
            tracer),
            open(Config.SAVE_FILE, "wb")
        )
        last_save = t

    if np.isnan(u.max()):
        sys.exit()

    # advance time by one timestep
    t += dt

    time_taken = float(round(time.time() - initial_time, 3))

    print('Time: ', str(time_taken), 's')
