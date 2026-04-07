import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from conversions import moment2magnitude

# Load the centroids data
centroids_df = pd.read_csv('/Users/francescoacolosimo/Desktop/MSc_thesis/Data/Kumamoto_6/fault_csv/grouped_centroids_data_with_magnitude.csv')

# Define the bin size (2 seconds)
bin_size = 0.2

# Determine the range of trup values
min_trup = centroids_df['trup'].min()
max_trup = centroids_df['trup'].max()

# Calculate the maximum end time to ensure all triangular functions complete
max_rise = centroids_df['rise'].max()
max_end_time = max_trup + (max_rise * 2)  # Add maximum duration to max trup

# Create bins for the trup values
bins = np.arange(min_trup, max_end_time + bin_size, bin_size)

# Create a time array for the source time function - extend to capture all triangular functions
time_array = np.arange(min_trup, max_end_time + bin_size, bin_size / 10)
num_points = 1000

# Function to create a triangular source time function
def triangular_source_time_function(trup, sf_moment, rise):
    duration = rise * 2 # Total duration is the sum of rise and fall times
    start_time = trup
    end_time = trup + duration
    peak_time = trup + rise  # Peak occurs after the rise time

    # Calculate the peak value to ensure the area equals sf_moment
    peak_value = (2 * sf_moment) / duration

    # Create a high-resolution time array
    times = np.linspace(start_time, end_time, num_points)

    # Create the triangular moment values
    moments = np.zeros_like(times)
    peak_index = int(num_points * (rise / duration))  # Index of the peak moment
    moments[:peak_index] = np.linspace(0, peak_value, peak_index)  # Rising edge
    moments[peak_index:] = np.linspace(peak_value, 0, num_points - peak_index)  # Falling edge

    return times, moments

# Initialize the source time function array
source_time_function = np.zeros_like(time_array)

# Distribute the moment for each cell over time using a triangular source time function
for index, row in centroids_df.iterrows():
    trup = row['trup']
    sf_moment = row['sf_moment']
    rise = row['rise']  # Use the rise column
    times, moments = triangular_source_time_function(trup, sf_moment, rise)
    source_time_function += np.interp(time_array, times, moments)

print(f"Source time function sum: {sum(source_time_function)}")
print(f"Time array range: {time_array.min():.2f} to {time_array.max():.2f} seconds")
print(f"Max trup: {max_trup:.2f}, Max rise: {max_rise:.2f}, Max end time: {max_end_time:.2f}")

# Create a figure and axis for the plot
fig, ax = plt.subplots(figsize=(10, 6))

# Plot the source time function
ax.plot(time_array, source_time_function, color='blue', label='Synthetic STF', linewidth=2)

# Load the moment rate data
moment_rate_data = np.loadtxt('/Users/francescoacolosimo/Desktop/MSc_thesis/Data/Kumamoto/moment_rate.mr')

# Plot the moment rate data
ax.plot(moment_rate_data[:, 0], moment_rate_data[:, 1] * 1e-7, color='red', label='Observed STF (USGS)', linewidth=2, zorder=1)

# Set plot labels and title
ax.set_xlabel('Time (s)')
ax.set_ylabel('Summed Sf Moment (N m)')
ax.set_title('Source Time Function Comparison')

# Add grid for better visualization
ax.grid(True, alpha=0.3)

# Calculate the total summed Sf Moment from the source time function
total_sf_moment_stf = np.trapz(source_time_function, time_array)
print(f"Total Summed Sf Moment (STF integration): {total_sf_moment_stf}")

# Calculate the total summed Sf Moment from centroids data
total_sf_moment_centroids = centroids_df['sf_moment'].sum()
print(f"Total Summed Sf Moment (centroids): {total_sf_moment_centroids}")

magnitude = moment2magnitude(total_sf_moment_centroids)
print(f"Magnitude grouped: {magnitude}")

USGS_moment = np.trapz(moment_rate_data[:, 1] * 1e-7, moment_rate_data[:, 0])
print(f"Total Summed Sf Moment USGS (integrated): {USGS_moment}")
USGS_magnitude = moment2magnitude(USGS_moment)
print(f"Magnitude USGS: {USGS_magnitude}")


plt.legend()
plt.tight_layout()
plt.show()

# Print final verification
print(f"\nFinal verification:")
print(f"STF ends at: {time_array[-1]:.2f} seconds")
print(f"Final STF value: {source_time_function[-1]:.2e}")
print(f"STF properly decays to zero: {abs(source_time_function[-1]) < 1e-10}")