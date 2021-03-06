import numpy as np
import matplotlib.pyplot as plt
import json

category_values = {
    # "sport": [5, 1, 0, 3, 2],
    # "computer": [2, 0, 5, 2, 4],
    "restaurant": [5, 0],
    "park": [0, 5],
}


def distance(a, b):
    return np.linalg.norm(np.array(a) - np.array(b))


def calculate_error(clusters):
    error = 0
    for cluster in clusters:
        clus_coord = [float(a) for a in cluster.split(' ')]
        current_err = sum([distance(np.array(clus_coord), x[1])**2 for x in clusters[cluster]])
        error += current_err
    return error


def recenter_centroids(centroids):
    new_centroids = []

    for centroid in centroids:
        labels, vectors = [x[0] for x in centroids[centroid]], [x[1] for x in centroids[centroid]]
        cluster_points = np.rot90(vectors, k=3)
        center_of_mass = np.sum(cluster_points, axis=1) / len(vectors)
        new_centroids.append(center_of_mass.tolist())
    return new_centroids


def display_points(values, centroids):
    for l, v in values.items():
        # print(l, v)
        x, y = v
        # get_color((x, y), centroids_dict)
        plt.plot(x, y, 'o', c=get_color(l, centroids))
        plt.text(x + 0.01, y + 0.01, l, fontsize=12)
    for centroid in centroids:
        x, y = centroid.split(" ")
        plt.plot(float(x), float(y), 'o', c='black')
        plt.text(float(x) + 0.01, float(y) + 0.01, "O", fontsize=12)
    plt.title(f"{len(values.values())} items, {len(centroids)} centroids")
    # plt.xlim([0, 6])
    # plt.ylim([0, 6])
    plt.show()


def find_elbow(points):
    """
    Must have more than 2 points.
    Calculates the elbow based on the change in slope.
    :param points: List of 2-D coordinates
    :return: Returns the X value of the elbow
    """
    delta_m = []

    points = [(0, 0)] + points + [(0, 0)]

    for i, point in enumerate(points[1:-1]):
        p_x, p_y = points[i]
        x, y = point
        n_x, n_y = points[x]
        m_before = y-p_y
        m_after = n_y-y
        delta_m.append(round(np.abs(m_before)-np.abs(m_after), 4))
        # print(f"{i+1} {delta_m[-1]}")
        if i > 2:
            if delta_m[-2] - delta_m[-1] > 0:
                # print(delta_m)
                break

    # # delta_m = [x if x < 0 else -100 for x in delta_m]
    # print(delta_m, delta_m.index(min(delta_m)))
    try:
        return delta_m.index(min(delta_m))
    except ValueError:
        return -1


class KMEANS:
    def __init__(self, vls=None, k: int = 0):

        if vls is None:
            vls = {}

        '''
        ### The values parameter should look like this:
                {
                    label: (x, y, z...), 
                    label2: (x, y, z...),
                    ...
                }
        '''
        self.values: dict = vls
        self.labels = list(self.values.keys())
        self.distances = np.array([])
        self.k: int = k
        self.origin = None
        self.groups: dict

    def group_clusters(self, centroid_coords):
        centroids = {}
        """
        Calculate the distance between a point and every centroid
        Find the closest one and label that point as belonging to that centroid
        """
        for label, vec in zip(self.labels, self.values.values()):
            # We want to remember the label (name) of each point
            min_dist, best_centroid = 10 ** 99, None

            # Loop over every centroid
            for center in centroid_coords:
                dist = distance(np.array(center), np.array(vec))
                if dist < min_dist:
                    # New closest centroid
                    min_dist = dist
                    best_centroid = center

            # Centroids are a tuple of floats, if we want it
            # to be hashable we convert it to a string
            temp = " ".join([str(x) for x in best_centroid])
            if temp not in centroids:
                centroids[temp] = []

            # if valid_distance(best_centroid, centroids[temp], vec):
            # if len(centroids[temp]) < 2:
            centroids[temp].append((label, vec))

        centroids = {k: v for (k, v) in centroids.items() if len(v) > 1}

        return centroids

    def find_optimal_clusters(self, *, reps=10, draw_graphs=False, get_error=False, only_these_values=None, verbose=False):
        if only_these_values is not None:
            save_values = self.values.copy()
            self.set_values(only_these_values)
            self.labels = list(self.values.keys())
        if verbose:
            print("Running on values: ", json.dumps(self.values, indent=2))
        results = [self.train(draw_graphs=draw_graphs) for _ in range(reps)]
        errors = [x[1] for x in results]
        best = errors.index(min(errors))
        if draw_graphs:
            display_points(self.values, results[best][0])
        ret = results[best] if get_error else results[best][0]
        if verbose:
            print("ret = \n\r", "\n".join([",".join([user[0] for user in ret[c]]) for c in ret]), "\n")

        if only_these_values is not None:
            self.values = save_values.copy()
            self.labels = list(self.values.keys())

        return ret

    def train(self, *, draw_graphs=False):
        error_values = []
        centroids_options = []
        length = len(list(self.values.keys()))
        for i in range(1, length):
            old_centroids_array = []
            # centroids_array = [[2.5 + 1.5 * np.cos(2*np.pi * j / i),
            #                     2.5 + 1.5 * np.sin(2*np.pi * j / i)] for j in range(i)]
            try:
                fixed_coords = np.rot90(list(self.values.values()), 3)
                max_corner = np.amax(fixed_coords, axis=1)
                min_corner = np.amin(fixed_coords, axis=1)
            except TypeError:
                print(self.values.values())
                break

            centroids_array = np.random.uniform(min_corner, max_corner, size=(i, len(max_corner)))

            centroids_dict = {}
            # print(f"Adjusting centroids...")
            while not np.all(centroids_array == old_centroids_array):
                # print(len(centroids_array), len(old_centroids_array), i)
                centroids_dict = self.group_clusters(centroids_array)

                # display_points(self.values, centroids_dict)

                old_centroids_array = centroids_array
                centroids_array = recenter_centroids(centroids_dict)

            # print(f"{i = } | ", calculate_error(centroids_dict))

            error_values.append(calculate_error(centroids_dict))
            centroids_options.append(centroids_dict)

        x = [i + 1 for i in range(len(error_values))]
        # print(centroids_options)
        elbow = find_elbow(list(zip(x, error_values)))
        # print("ELBOW =", elbow)
        # if elbow >
        if elbow == -1:
            return {}, 10**99
        return centroids_options[elbow], error_values[elbow]

    def set_origin(self, name):
        self.origin = name

    def set_values(self, vls):
        self.values = vls

    def _euclidean_dist(self, target_point: np.array) -> float:
        try:
            if self.origin in self.values:
                return distance(np.array(self.values[self.origin]), np.array(target_point))
            else:
                return distance(np.array(self.origin), np.array(target_point))
        except TypeError:
            return distance(self.origin, np.array(target_point))

    def get_closest(self, n=None, weigh_values=None, only_these_values=None,
                    names_only=False, verbose=False, remove_first=True):
        """
        :param remove_first: remove the first result (not include the person in question)
        :param verbose: make function print things
        :param names_only: only return names, not coordinates
        :param only_these_values: only run on certain values
        :param weigh_values: user-controlled function to weigh the
        :param n: Number of nearest neighbours to return
        :return: K-NN labels
        """
        assert self.origin is not None
        saved_values = None
        if only_these_values is not None:
            saved_values = self.values
            self.values = only_these_values

        labels = list(self.values.keys())
        vectors = list(self.values.values())
        if weigh_values is None:
            distances = [self._euclidean_dist(np.array(vector)) for vector in vectors]
        else:
            distances = [weigh_values(label, self._euclidean_dist(np.array(vector)))
                         for label, vector in zip(labels, vectors)]

        labeled_distances = [(label, dist) for label, dist in zip(labels, distances)]

        labeled_distances.sort(key=lambda info: info[1])
        if verbose:
            print(self.origin, [x[0] for x in labeled_distances])
        save_k = self.k
        if n is None and self.k == 0:
            n = int(np.sqrt(len(self.values)))
        elif n is None:
            n = self.k
            # self.k = n
        else:
            self.k = n
            # n = self.k

        final_values = labeled_distances[1:n] if remove_first else labeled_distances[:n]

        if only_these_values is not None:
            self.values = saved_values

        if names_only:
            return [x[0] for x in final_values]

        self.k = save_k
        return final_values

    def find_best_category(self, people, categories, center=None):
        if center is None:
            center = np.array([self.values[person] for person in people])
            center = np.sum(center, axis=0) / center.shape[0]

        self.set_origin(center)
        distances = [(category_name, self._euclidean_dist(categories[category_name]))
                     for category_name in categories]

        return sorted(distances, key=lambda x: x[1])[0][0]


def get_intersection(a, b):
    return list(set(a) & set(b))


def get_color(target, clusters, add):
    # colors = ['green', 'orange', 'fuchsia', 'magenta', 'olive', 'teal', 'violet',
    #          'skyblue', 'gray', 'darkorange', 'cyan', 'royal_blue']
    colors = ['blu', 'grn', 'pink', 'whit', 'purple']
    for i, cluster in enumerate(clusters):
        if target in [b[0] for b in clusters[cluster]]:
            return colors[i+add]
    return 'red'


if __name__ == "__main__":
    values = {
        "Dan": [5, 5],
        "Rudich": [4, 4],
        "Guy": [4.5, 4],
        "Shoshani": [4, 5],
        #
        "Fefer": [1, 2],
        "Maya": [2, 2],
        "Yasha": [1, 1],
        "Eran": [2.5, 2.5],
        #
        "Yael": [5, 0.9],
        "Dana": [4.5, 0.2],

        "Danilin": [1, 5],
        "Omer": [1.5, 4.6],
        "Manor": [0.5, 4]
    }
    # sport|theater|computer|park|restaurant|

    kmeans = KMEANS(values)

    kmeans.set_origin("Dan")
    a = kmeans.find_optimal_clusters(draw_graphs=True)

    # i = 3
    # x = [3 + 1.5 * np.cos(2 * np.pi * j / i+0.25) for j in range(i)]
    # y = [3 + 1.5 * np.sin(2 * np.pi * j / i+0.25) for j in range(i)]
    # plt.scatter(x, y)
    # plt.show()
